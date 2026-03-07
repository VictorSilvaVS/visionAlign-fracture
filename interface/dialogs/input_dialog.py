from PyQt5.QtWidgets import QInputDialog, QWidget

class InputDialog:
    """
    Um wrapper simples para QInputDialog para facilitar o uso
    e manter a consistência com outras caixas de diálogo personalizadas.
    """

    @staticmethod
    def getText(parent: QWidget, title: str, label: str, text: str = "") -> tuple[str, bool]:
        """
        Exibe um diálogo de entrada de texto padrão.
        """
        return QInputDialog.getText(parent, title, label, text=text)