"""RDKit Structure Renderer Service

出版级分子结构渲染。SMILES → SVG（矢量可缩放，适用于论文）。
"""
import logging

logger = logging.getLogger(__name__)


class RDKitRenderer:
    """RDKit 2D 结构渲染器 — 出版级 SVG 输出"""

    @staticmethod
    def render_svg(
        smiles: str,
        width: int = 500,
        height: int = 400,
        bond_line_width: float = 2.0,
        add_atom_indices: bool = False,
    ) -> str:
        """SMILES → 出版级 SVG。

        Args:
            smiles: SMILES 字符串
            width: SVG 宽度 (px)
            height: SVG 高度 (px)
            bond_line_width: 键线宽度（默认 2.0，适合出版）
            add_atom_indices: 是否标注原子序号

        Returns:
            SVG 字符串（失败时返回空字符串）
        """
        try:
            from rdkit import Chem
            from rdkit.Chem.Draw import MolDraw2DSVG
            from rdkit.Chem.Draw import rdMolDraw2D

            mol = Chem.MolFromSmiles(smiles)
            if mol is None:
                logger.warning(f"RDKit cannot parse SMILES: {smiles[:60]}")
                return ""

            # Compute 2D coordinates if not present
            if not mol.GetNumConformers():
                from rdkit.Chem import AllChem
                mol = Chem.MolFromSmiles(smiles)  # fresh copy
                AllChem.Compute2DCoords(mol)

            drawer = MolDraw2DSVG(width, height)
            opts = drawer.drawOptions()
            opts.bondLineWidth = bond_line_width
            opts.addAtomIndices = add_atom_indices
            # Higher quality font rendering
            opts.useMolBlockWedging = False

            drawer.DrawMolecule(mol)
            drawer.FinishDrawing()
            svg = drawer.GetDrawingText()
            return svg

        except Exception as e:
            logger.warning(f"RDKit render failed: {e}")
            return ""

    @staticmethod
    def render_png(smiles: str, width: int = 600, height: int = 480) -> bytes:
        """SMILES → 高分辨率 PNG 二进制数据。

        失败时返回空 bytes。
        """
        try:
            from rdkit import Chem
            from rdkit.Chem.Draw import MolDraw2DCairo

            mol = Chem.MolFromSmiles(smiles)
            if mol is None:
                return b""

            from rdkit.Chem import AllChem
            AllChem.Compute2DCoords(mol)

            drawer = MolDraw2DCairo(width, height)
            opts = drawer.drawOptions()
            opts.bondLineWidth = 2.5
            drawer.DrawMolecule(mol)
            drawer.FinishDrawing()
            return drawer.GetDrawingText()

        except Exception as e:
            logger.warning(f"RDKit PNG render failed: {e}")
            return b""

    @staticmethod
    def validate_smiles(smiles: str) -> dict:
        """SMILES 校验和标准化。

        Returns:
            { valid: bool, canonical: str, error: str|null }
        """
        try:
            from rdkit import Chem
            mol = Chem.MolFromSmiles(smiles)
            if mol is None:
                return {"valid": False, "canonical": "", "error": "Cannot parse SMILES"}
            canonical = Chem.MolToSmiles(mol, canonical=True)
            return {"valid": True, "canonical": canonical, "error": None}
        except Exception as e:
            return {"valid": False, "canonical": "", "error": str(e)}
