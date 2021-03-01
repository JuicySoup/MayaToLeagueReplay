import MLTRUI
import pymel.core as pm
from PySide2 import QtCore

callback = None
window = None


"""
OLD FUNCTION - DEPRECATED
def main():
    reload(MTLR)
    global callback
    try:
        OpenMaya.MMessage.removeCallback(callback)
        OpenMaya.MGlobal.displayWarning("Removed callback")
    except RuntimeError:
        commands = MTLR.MayaToLeagueReplay()
        callback = OpenMaya.MTimerMessage.addTimerCallback(1.0 / 60, commands.get_pos)
        OpenMaya.MGlobal.displayWarning("Added callback")"""


# script for opening the QDialog
def show_ui():
    # apply changes to the ui
    reload(MLTRUI)
    # we need to keep a reference to the window so we store it in a global variable
    global window

    """attempt to close the old window to trigger cleanup, if the variable doesn't exist just pass. 
    If it managed to close the window, delete the workspace control to not clutter mayas ui 
    (Object name has to be set for this to work properly)"""
    try:
        window.close()
    except AttributeError:
        pass
    else:
        pm.deleteUI(window.objectName() + "WorkspaceControl")

    # instantiate UI class and make sure it gets deleted when closed
    window = MLTRUI.UI()
    window.setAttribute(QtCore.Qt.WA_DeleteOnClose)
    # show the UI and making it dockable
    # setting the width to 0 ensures that the window is set to the smallest size possible
    window.show(dockable=True, w=0)
