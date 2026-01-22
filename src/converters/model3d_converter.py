"""
3D Model Converter - handles OBJ, FBX, GLB, GLTF, STL, DAE
Uses trimesh and pygltflib for conversions
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import trimesh

from .base import BaseConverter, ConversionResult

logger = logging.getLogger(__name__)


class Model3DConverter(BaseConverter):
    """Converter for 3D model formats"""

    @property
    def supported_input_formats(self) -> set:
        return {"obj", "stl", "glb", "gltf", "ply", "off", "dae"}

    @property
    def supported_output_formats(self) -> set:
        return {"obj", "stl", "glb", "gltf", "ply"}

    async def convert(
        self,
        input_path: Path,
        output_format: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> ConversionResult:
        """Convert 3D model to specified format"""
        start_time = datetime.now()
        options = options or {}

        try:
            self.validate_input(input_path)
            input_format = input_path.suffix.lstrip(".").lower()
            output_format = output_format.lower()

            output_path = self.get_output_path(input_path, output_format)

            # Load the mesh
            mesh = trimesh.load(str(input_path), force="mesh")

            # Apply transformations if requested
            mesh = self._apply_transformations(mesh, options)

            # Export to target format
            self._export_mesh(mesh, output_path, output_format, options)

            elapsed = (datetime.now() - start_time).total_seconds()

            return ConversionResult(
                success=True,
                input_path=input_path,
                output_path=output_path,
                input_format=input_format,
                output_format=output_format,
                conversion_time=elapsed,
                file_size=self.get_file_size(output_path),
            )

        except Exception as e:
            logger.error(f"3D model conversion failed: {e}")
            return ConversionResult(
                success=False,
                input_path=input_path,
                input_format=input_path.suffix.lstrip("."),
                output_format=output_format,
                error_message=str(e),
            )

    def _apply_transformations(
        self, mesh: trimesh.Trimesh, options: dict
    ) -> trimesh.Trimesh:
        """Apply optional transformations to mesh"""
        # Scale
        if "scale" in options:
            scale = options["scale"]
            if isinstance(scale, (int, float)):
                mesh.apply_scale(scale)
            elif isinstance(scale, (list, tuple)):
                mesh.apply_scale(scale)

        # Rotation (degrees)
        if "rotate" in options:
            rotation = options["rotate"]
            if "x" in rotation:
                angle = np.radians(rotation["x"])
                rot_matrix = trimesh.transformations.rotation_matrix(angle, [1, 0, 0])
                mesh.apply_transform(rot_matrix)
            if "y" in rotation:
                angle = np.radians(rotation["y"])
                rot_matrix = trimesh.transformations.rotation_matrix(angle, [0, 1, 0])
                mesh.apply_transform(rot_matrix)
            if "z" in rotation:
                angle = np.radians(rotation["z"])
                rot_matrix = trimesh.transformations.rotation_matrix(angle, [0, 0, 1])
                mesh.apply_transform(rot_matrix)

        # Center the mesh
        if options.get("center", False):
            mesh.vertices -= mesh.centroid

        return mesh

    def _export_mesh(
        self,
        mesh: trimesh.Trimesh,
        output_path: Path,
        output_format: str,
        options: dict,
    ):
        """Export mesh to specified format"""
        if output_format == "obj":
            mesh.export(str(output_path), file_type="obj")

        elif output_format == "stl":
            # STL can be ASCII or binary
            binary = options.get("binary", True)
            if binary:
                mesh.export(str(output_path), file_type="stl")
            else:
                mesh.export(str(output_path), file_type="stl_ascii")

        elif output_format == "glb":
            mesh.export(str(output_path), file_type="glb")

        elif output_format == "gltf":
            mesh.export(str(output_path), file_type="gltf")

        elif output_format == "ply":
            mesh.export(str(output_path), file_type="ply")

        else:
            # Try generic export
            mesh.export(str(output_path))

    async def get_model_info(self, input_path: Path) -> dict:
        """Get 3D model information"""
        try:
            mesh = trimesh.load(str(input_path), force="mesh")
            return {
                "vertices": len(mesh.vertices),
                "faces": len(mesh.faces),
                "bounds": mesh.bounds.tolist(),
                "center": mesh.centroid.tolist(),
                "volume": float(mesh.volume) if mesh.is_watertight else None,
                "is_watertight": mesh.is_watertight,
                "euler_number": mesh.euler_number,
            }
        except Exception as e:
            logger.error(f"Failed to get model info: {e}")
            return {}

    async def simplify_mesh(
        self, input_path: Path, output_path: Path, target_faces: int = 10000
    ) -> bool:
        """Simplify mesh by reducing face count"""
        try:
            mesh = trimesh.load(str(input_path), force="mesh")

            # Use quadric decimation if available
            if len(mesh.faces) > target_faces:
                mesh = mesh.simplify_quadric_decimation(target_faces)

            output_format = output_path.suffix.lstrip(".").lower()
            mesh.export(str(output_path), file_type=output_format)
            return True
        except Exception as e:
            logger.error(f"Mesh simplification failed: {e}")
            return False
