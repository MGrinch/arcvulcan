from __future__ import annotations

import hashlib
import os
import secrets
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .embeddings import safe_normalize


# ------------------------------------------------------------------------------
# SECTOR 0: THE OMEGA LITHOSPHERE (UNTOUCHED BEDROCK)
# ------------------------------------------------------------------------------

DEFAULT_SEED = 42
DEFAULT_MASTERY = 0.5


@dataclass(frozen=True)
class LithosphereEntry:
    """Public immutable view of a stored lithosphere node."""

    node_id: str
    tensor: np.ndarray
    projection_3d: np.ndarray
    mastery: float
    text_hash: str


@dataclass(frozen=True)
class _InternalEntry:
    """Internal immutable storage record for projected node data."""

    node_id: str
    tensor: np.ndarray
    projection_3d: np.ndarray
    text_hash: str


class Lithosphere:
    """Deterministic per-node vector store with DNA-style projections."""

    def __init__(
        self,
        *,
        embed_dim: int = 768,
        grains: int = 8,
        seed: int | None = None,
        path_prefix: str | None = None,
        dna_filename: str = "dna_geometry.bin",
        projection_scale: float = 10.0,
    ) -> None:
        """Initialize the lithosphere with deterministic DNA geometry."""
        if embed_dim <= 0:
            raise ValueError('embed_dim must be positive')
        if grains <= 0:
            raise ValueError('grains must be positive')

        self.embed_dim = int(embed_dim)
        self.grains = int(grains)
        self.seed = DEFAULT_SEED if seed is None else int(seed)
        self.path_prefix = path_prefix
        self.dna_filename = str(dna_filename or "dna_geometry.bin")
        self.projection_scale = float(projection_scale)
        self._rng = np.random.default_rng(self.seed)
        self._entries: dict[str, _InternalEntry] = {}
        self._mastery: dict[str, float] = {}
        self._meta: dict[int, dict[str, str]] = {}
        self._node_indices: dict[str, int] = {}
        self.dna_loaded = False

        dna_path = self.dna_path
        if dna_path is not None and self._load_dna(dna_path):
            self.dna_loaded = True
        else:
            self.P, self.R = self._generate_dna()
            if dna_path is not None:
                self._save_dna(dna_path)

    def _generate_dna(self) -> tuple[np.ndarray, np.ndarray]:
        """Create deterministic projection matrices for tensor and 3D views."""
        random_matrix = self._rng.standard_normal((self.embed_dim, self.grains), dtype=np.float32)
        q_matrix, _ = np.linalg.qr(random_matrix)
        p_matrix = np.asarray(q_matrix, dtype=np.float32)

        r_matrix = self._rng.standard_normal((3, self.embed_dim), dtype=np.float32)
        r_matrix = np.asarray(r_matrix / np.sqrt(float(self.embed_dim)), dtype=np.float32)
        return p_matrix, r_matrix

    @property
    def dna_path(self) -> Path | None:
        """Return the configured on-disk DNA path, if persistence is enabled."""
        if self.path_prefix is None:
            return None
        base_dir = Path(self.path_prefix) if self.path_prefix else Path(".")
        return base_dir / self.dna_filename

    def _load_dna(self, path: Path) -> bool:
        """Load persisted DNA geometry from disk when a matching file exists."""
        try:
            raw = path.read_bytes()
        except OSError:
            return False

        p_bytes = self.embed_dim * self.grains * np.dtype(np.float32).itemsize
        r_bytes = 3 * self.embed_dim * np.dtype(np.float32).itemsize
        if len(raw) != p_bytes + r_bytes:
            return False

        try:
            p_matrix = np.frombuffer(raw[:p_bytes], dtype=np.float32).copy().reshape((self.embed_dim, self.grains))
            r_matrix = np.frombuffer(raw[p_bytes:], dtype=np.float32).copy().reshape((3, self.embed_dim))
        except ValueError:
            return False

        self.P = np.asarray(p_matrix, dtype=np.float32)
        self.R = np.asarray(r_matrix, dtype=np.float32)
        return True

    def _save_dna(self, path: Path | None = None) -> None:
        """Persist DNA geometry atomically as P bytes followed by R bytes."""
        dna_path = path or self.dna_path
        if dna_path is None:
            raise ValueError("path_prefix is required to persist DNA geometry")
        dna_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = dna_path.with_name(f"{dna_path.name}.tmp.{os.getpid()}.{secrets.token_hex(8)}")
        fd = None
        try:
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            fd = os.open(str(tmp), flags, 0o600)
            with os.fdopen(fd, "wb") as f:
                fd = None
                f.write(np.asarray(self.P, dtype=np.float32).tobytes())
                f.write(np.asarray(self.R, dtype=np.float32).tobytes())
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, dna_path)
        finally:
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass

    def get_or_create(self, node_id: str, vector: list[float], text: str) -> LithosphereEntry:
        """Return an existing node entry or create a new deterministic one."""
        if node_id in self._entries:
            return self._public_entry(self._entries[node_id])

        vector_np = self._coerce_vector(vector)
        tensor = self._project_tensor(vector_np)
        projection_3d = np.asarray((self.R @ vector_np) * self.projection_scale, dtype=np.float32)
        text_hash = self._hash_text(text)

        idx = len(self._entries)
        internal_entry = _InternalEntry(
            node_id=node_id,
            tensor=tensor,
            projection_3d=projection_3d,
            text_hash=text_hash,
        )
        self._entries[node_id] = internal_entry
        self._mastery[node_id] = DEFAULT_MASTERY
        self._node_indices[node_id] = idx
        self._meta[idx] = {'jid': node_id, 'text': text}
        return self._public_entry(internal_entry)

    def compute_resonance(self, node_id: str, input_vector: list[float]) -> float:
        """Compute the resonance between an input vector and a stored node tensor."""
        entry = self._entries.get(node_id)
        if entry is None:
            return 0.0

        projected_input = self._project_tensor(self._coerce_vector(input_vector))
        resonance = float(np.dot(projected_input, entry.tensor))
        return self._clamp(resonance, lower=-1.0, upper=1.0)

    def update_mastery(
        self,
        node_id: str,
        *,
        resonance: float,
        text_similarity: float,
        res_threshold: float = 0.9,
        sim_threshold: float = 0.95,
        increment: float = 0.1,
    ) -> float:
        """Update mastery when resonance or text similarity crosses threshold."""
        current = self.get_mastery(node_id)
        if node_id not in self._entries:
            return current

        should_increment = float(resonance) > float(res_threshold) or float(text_similarity) > float(sim_threshold)
        if should_increment:
            current = min(1.0, current + max(0.0, float(increment)))
            self._mastery[node_id] = current
        return float(current)

    def get_entry(self, node_id: str) -> LithosphereEntry | None:
        """Return a frozen public snapshot for a stored node, if present."""
        entry = self._entries.get(node_id)
        if entry is None:
            return None
        return self._public_entry(entry)

    def get_meta(self, node_id: str) -> dict[str, str] | None:
        """Return stored metadata for a node, if present."""
        idx = self._node_indices.get(node_id)
        if idx is None:
            return None
        meta = self._meta.get(idx)
        if meta is None:
            return None
        return dict(meta)

    def set_meta(self, node_id: str, meta: dict[str, object] | None) -> None:
        """Replace stored node metadata."""
        idx = self._node_indices.get(node_id)
        if idx is None:
            return
        self._meta[idx] = {} if meta is None else dict(meta)

    def get_mastery(self, node_id: str) -> float:
        """Return mastery for a node, defaulting to the lithosphere baseline."""
        return float(self._mastery.get(node_id, DEFAULT_MASTERY))

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable audit snapshot of the lithosphere state."""
        entries: dict[str, dict[str, object]] = {}
        for node_id, entry in self._entries.items():
            entries[node_id] = {
                'node_id': entry.node_id,
                'tensor': entry.tensor.tolist(),
                'projection_3d': entry.projection_3d.tolist(),
                'mastery': self.get_mastery(node_id),
                'text_hash': entry.text_hash,
            }
        return {
            'embed_dim': self.embed_dim,
            'grains': self.grains,
            'seed': self.seed,
            'projection_scale': self.projection_scale,
            'dna_loaded': self.dna_loaded,
            'dna_path': str(self.dna_path) if self.dna_path is not None else None,
            'meta': {node_id: self.get_meta(node_id) for node_id in self._entries},
            'entries': entries,
        }

    def _public_entry(self, entry: _InternalEntry) -> LithosphereEntry:
        """Convert an internal entry into the frozen public API shape."""
        return LithosphereEntry(
            node_id=entry.node_id,
            tensor=entry.tensor.copy(),
            projection_3d=entry.projection_3d.copy(),
            mastery=float(self._mastery.get(entry.node_id, DEFAULT_MASTERY)),
            text_hash=entry.text_hash,
        )

    def _coerce_vector(self, vector: list[float]) -> np.ndarray:
        """Clip and resize a user vector to the configured embedding size."""
        vector_np = np.asarray(vector, dtype=np.float32).reshape(-1)
        if vector_np.size == 0:
            vector_np = np.zeros(self.embed_dim, dtype=np.float32)
        if vector_np.size != self.embed_dim:
            vector_np = np.resize(vector_np, self.embed_dim)
        vector_np = np.clip(vector_np, -1.0, 1.0)
        return np.asarray(vector_np, dtype=np.float32)

    def _project_tensor(self, vector: np.ndarray) -> np.ndarray:
        """Project a vector into the flattened grain tensor space."""
        grain_positions = np.arange(1, self.grains + 1, dtype=np.float32)
        projected = np.outer(vector, grain_positions) * self.P
        flattened = np.asarray(projected.reshape(-1), dtype=np.float32)
        normalized = safe_normalize(flattened)
        return np.asarray(normalized, dtype=np.float32)

    def _hash_text(self, text: str) -> str:
        """Return a deterministic SHA-256 hash for the stored text."""
        return hashlib.sha256(text.encode('utf-8')).hexdigest()

    def _clamp(self, value: float, *, lower: float, upper: float) -> float:
        """Clamp a float into a closed interval."""
        if value < lower:
            return lower
        if value > upper:
            return upper
        return value
