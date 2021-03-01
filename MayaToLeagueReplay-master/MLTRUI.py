from maya.api import OpenMaya, OpenMayaAnim
from maya import OpenMayaUI as O_OMUI
from maya.app.general import mayaMixin
from PySide2 import QtWidgets, QtGui, QtCore
from shiboken2 import wrapInstance
from functools import partial
import pymel.core as pm
import os
import MTLR
reload(MTLR)

maya_useNewAPI = True


# qt gui class, also inherit from MayaQWidgetDockableMixin to make it dockable
# noinspection PyAttributeOutsideInit,PyUnusedLocal
class UI(mayaMixin.MayaQWidgetDockableMixin, QtWidgets.QDialog):

    def __init__(self, parent=None):
        super(UI, self).__init__(parent)

        self.setWindowTitle('Maya to League Replay')
        # set the object name to ensure safe deletion
        self.setObjectName("MLTRUI")
        MTLR.TimeSliderCallback.ui = self
        self.callback = None
        self.mode = None
        self.commands = MTLR.MayaToLeagueReplay()
        MTLR.TimeSliderCallback.ui = self
        # get path of the Icon folder by grabbing the current file location
        self.icons = os.path.join(os.path.dirname(__file__), "assets/icons")
        self.fonts = os.path.join(os.path.dirname(__file__), "assets/fonts")
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.buildui()

        self.main_layout.addItem(QtWidgets.QSpacerItem(0, 0, QtWidgets.QSizePolicy.Fixed,
                                                       QtWidgets.QSizePolicy.Expanding))

        self.status = QtWidgets.QStatusBar()
        self.main_layout.addWidget(self.status)

        """skipping time in the replay is not instant, so we should limit the rate a bit. We do this by only updating
        when finishing scrubbing on the timeline. However, maya doesn't have a callback for when you finish scrubbing
        so we implement it by adding an event to the time slider"""
        slider = pm.mel.eval('$tmpVar=$gPlayBackSlider')
        ptr = O_OMUI.MQtUtil.findControl(slider)
        self.widget = wrapInstance(long(ptr), QtWidgets.QWidget)
        # then we simply instantiate the event filter we created in MLTR and install it
        self.filter = MTLR.TimeSliderCallback()
        self.widget.installEventFilter(self.filter)

        # then we need to connect maya's playback to leagues with a callback
        self.playing_callback = OpenMaya.MConditionMessage.addConditionCallback("playingBack", self.update_playing)

    # I use a separate method to add elements to the QDialog; can be put into the __init__ as well
    def buildui(self):
        fixed = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)

        title = QtWidgets.QLabel("Maya To League Replay")
        title.setStyleSheet("QLabel{font-size: 18px; font-weight: bold}")
        title.setAlignment(QtCore.Qt.AlignCenter)
        self.main_layout.addWidget(title)

        live_link = GroupBox("Live Link")
        link_layout = QtWidgets.QGridLayout(live_link)
        self.camera_name = QtWidgets.QLineEdit()
        self.camera_name.setPlaceholderText("Camera Name")
        self.camera_name.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
        self.camera_name.setReadOnly(True)
        link_layout.addWidget(self.camera_name, 0, 0, 1, 2)

        grab_cam_btn = QtWidgets.QPushButton("Grab Camera")
        grab_cam_btn.clicked.connect(self.grab_camera)
        link_layout.addWidget(grab_cam_btn, 0, 2, 1, 1)

        create_cam_btn = QtWidgets.QPushButton("Create Camera")
        create_cam_btn.clicked.connect(self.create_cam)
        link_layout.addWidget(create_cam_btn, 0, 3)

        self.time_link = QtWidgets.QCheckBox("Time Link")
        self.time_link.setSizePolicy(fixed)
        link_layout.addWidget(self.time_link, 0, 4)

        self.tick_rate = QtWidgets.QSpinBox()
        self.tick_rate.setMinimum(1)
        self.tick_rate.setMaximum(200)
        self.tick_rate.setValue(60)
        self.tick_rate.setSizePolicy(fixed)
        link_layout.addWidget(self.tick_rate, 1, 0)

        self.start_btn = QtWidgets.QPushButton("Start")
        icon = QtGui.QIcon("{}/play.png".format(self.icons))
        self.start_btn.setIcon(icon)
        self.start_btn.clicked.connect(self.register_callback)
        link_layout.addWidget(self.start_btn, 1, 1, 1, 4)

        json_group = GroupBox("League Director Integration")
        json_layout = QtWidgets.QHBoxLayout(json_group)

        time_btn = QtWidgets.QPushButton("Adjust Timeline")
        time_btn.clicked.connect(self.update_time)
        json_layout.addWidget(time_btn)

        import_btn = QtWidgets.QPushButton("Import Keyframes")
        json_layout.addWidget(import_btn)

        export_btn = QtWidgets.QPushButton("Export Keyframes")
        json_layout.addWidget(export_btn)

        self.main_layout.addWidget(live_link)
        self.main_layout.addWidget(json_group)

    # method that gets triggered whenever the gui closes, used for cleanup
    def dockCloseEventTriggered(self):
        self.remove_callback()
        OpenMaya.MMessage.removeCallback(self.playing_callback)
        self.widget.removeEventFilter(self.filter)
        self.dof_cleanup()

    def dof_cleanup(self):
        try:
            self.DoF.cleanup()
        except AttributeError:
            pass
        else:
            self.show_status("DoF Callback removed")
        self.DoF = None

    # noinspection PyUnresolvedReferences
    @staticmethod
    def create_cam():
        try:
            pm.leagueCam()
        except AttributeError:
            try:
                pm.loadPlugin("createCamera")
            except RuntimeError:
                OpenMaya.MGlobal.displayError("Plugin not found, did you install it correctly?")
                return
            pm.leagueCam()

    def update_playing(self, *args, **kwargs):
        if not self.time_link.isChecked():
            return
        # define quick dictionary so we don't update any other values
        playback = {
            "paused": not OpenMayaAnim.MAnimControl.isPlaying()
        }
        # do the post request
        self.commands.post("playback", playback)

    def update_time(self):
        # grab the current time in league
        reply = self.commands.get("playback")
        # once finished, update maya's values
        reply.finished.connect(partial(self.commands.update_maya, reply))

    def show_status(self, message, time=5000):
        # quick method for showing status bar messages
        self.status.showMessage(message, time)

    def grab_camera(self):
        try:
            selection = OpenMaya.MGlobal.getActiveSelectionList().getDependNode(0)
        except IndexError:
            self.show_status("Error: Nothing selected")
            return
        name = OpenMaya.MFnDependencyNode(selection).absoluteName()
        # if possible, do some cleanup so the ui looks a bit better
        if name.startswith(":"):
            name = name.replace(":", "", 1)
        self.camera_name.setText(name)

        self.dof_cleanup()
        try:
            dag = OpenMaya.MFnDagNode(selection)
            dag.findPlug("dofSep", False)
        except:
            self.show_status("No suitable camera for DoF found")
        else:
            self.DoF = MTLR.DoF(selection)

    def register_callback(self):
        if not self.camera_name.text():
            self.show_status("Error: No camera selected")
            return
        if self.callback is not None:
            self.remove_callback()
        else:
            self.callback = OpenMaya.MTimerMessage.addTimerCallback(1.0 / self.tick_rate.value(),
                                                                    self.commands.set_pos,
                                                                    self.camera_name)
            # when adding the callback also set the button icon and text
            icon = QtGui.QIcon("{}/stop.png".format(self.icons))
            self.start_btn.setIcon(icon)
            self.start_btn.setText("Stop")
            self.tick_rate.setEnabled(False)
            # quick debug message
            OpenMaya.MGlobal.displayWarning("Successfully added callback")

    def remove_callback(self):
        # just attempt to remove the callback, if it doesn't work ignore it
        try:
            OpenMaya.MMessage.removeCallback(self.callback)
        except (TypeError, RuntimeError):
            pass
        else:
            # reset self.callback to None so the check in register_callback() works as intended
            self.callback = None
            # once again change the button's icon and text
            icon = QtGui.QIcon("{}/play.png".format(self.icons))
            self.start_btn.setText("Start")
            self.start_btn.setIcon(icon)
            self.tick_rate.setEnabled(True)
            # quick debug message
            OpenMaya.MGlobal.displayWarning("Successfully removed callback")


class GroupBox(QtWidgets.QGroupBox):

    def __init__(self, name):
        super(GroupBox, self).__init__(name)
        self.setStyle(QtWidgets.QStyleFactory.create("plastique"))
        self.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
