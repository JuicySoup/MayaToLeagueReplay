import pymel.core as pm


class UndoStack(object):

    def __init__(self, name=""):
        self.name = name

    def __enter__(self):
        pm.undoInfo(openChunk=True, infinity=True, cn=self.name)

    def __exit__(self, exc_type, exc_val, exc_tb):
        pm.undoInfo(closeChunk=True)
