from apps.assets.models import PdfFile


class AssetService:
    """资产层域服务"""

    @staticmethod
    def register_pdf(file_path: str, checksum: str = '') -> PdfFile:
        """注册 PDF 文件"""
        return PdfFile.objects.create(file=file_path, checksum=checksum)
