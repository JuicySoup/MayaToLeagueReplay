from maya.api import OpenMaya, OpenMayaAnim
from PySide2 import QtCore, QtNetwork
import json
import math
import time
import ReplayApiData

# necessary variable to tell maya to use OpenMaya Api 2.0
maya_useNewAPI = True


# class for time link (skipping)
# noinspection PyMethodOverriding
class TimeSliderCallback(QtCore.QObject):
    """we should keep a reference to the ui so we don't have to instantiate classes over and over again so we set
    this variable to the instance of the ui class in it's __init__ function"""
    ui = None

    def eventFilter(self, obj, event):
        # check if should be enabled
        if self.ui.time_link.isChecked():
            # check if left mouse button was released
            if event.type() == QtCore.QEvent.MouseButtonRelease and event.button() == QtCore.Qt.LeftButton:
                # get time in seconds
                current_time = OpenMayaAnim.MAnimControl.currentTime().asUnits(3)
                self.ui.commands.playback["time"] = current_time
                self.ui.commands.post("playback")
        # return False so whatever eventFilter was already installed by maya can still handle the same event
        return False


class Requests(object):
    def __init__(self):
        super(Requests, self).__init__()

        # use qt for http requests, type has to be set to application/json
        self.request = QtNetwork.QNetworkRequest()
        self.request.setHeader(QtNetwork.QNetworkRequest.ContentTypeHeader, "application/json")
        self.manager = QtNetwork.QNetworkAccessManager()

        # grab dictionary template
        self.render = ReplayApiData.render
        self.playback = ReplayApiData.playback
        self.fov = ReplayApiData.fov

    # method for get requests
    def get(self, url):
        # need to change the url to grab values
        self.request.setUrl(QtCore.QUrl(ReplayApiData.urls[url]))
        reply = self.manager.get(self.request)
        reply.ignoreSslErrors()
        return reply

    # method for updating the values in league
    def post(self, url, options=None):
        # a dictionary that stores the data dictionaries so we can parse arguments easier
        data_dict = {
            "render": self.render,
            "playback": self.playback,
            "fov": self.fov
        }
        self.request.setUrl(QtCore.QUrl(ReplayApiData.urls[url]))
        # we need to do a post request with our data as json
        if options is not None:
            reply = self.manager.post(self.request, json.dumps(options))
        else:
            reply = self.manager.post(self.request, json.dumps(data_dict[url]))
        # league client is using a self-signed certificate which will throw an ssl error, simply ignore it
        reply.ignoreSslErrors()


# noinspection PyUnusedLocal
class MayaToLeagueReplay(Requests):
    def __init__(self):
        super(MayaToLeagueReplay, self).__init__()

    def get_pos(self, camera):
        # get currently selected object via the api - just a temporary solution
        sel_list = OpenMaya.MSelectionList()
        sel_list.add(camera.text())
        obj = sel_list.getDependNode(0)

        # grab transform values, x has to be flipped because the in-game map is flipped along the y axis
        transform = OpenMaya.MFnTransform(obj).translation(1)
        self.render["cameraPosition"]["x"] = transform[0] * -1
        self.render["cameraPosition"]["y"] = transform[1]
        self.render["cameraPosition"]["z"] = transform[2]

        # grab euler rotation and change rotation order to zxy to be compatible with league
        euler = OpenMaya.MFnTransform(obj).rotation().reorder(2)
        # convert euler to angles
        angles = [math.degrees(angle) for angle in (euler.x, euler.y, euler.z)]
        # camera in league is flipped, therefore we need to apply x to y as well as multiplying them by -1 and
        # adding 180 to X
        self.render["cameraRotation"]["x"] = (angles[1] + 180) * -1
        self.render["cameraRotation"]["y"] = angles[0] * -1
        self.render["cameraRotation"]["z"] = angles[2]

    # method for getting camera values
    def set_pos(self, camera, *args, **kwargs):
        self.get_pos(camera)
        self.post("render")

    # there's no need to instantiate the class for this method, so just mark it as static
    @staticmethod
    def update_maya(reply):
        data = json.loads(reply.readAll().data().decode())
        length = OpenMaya.MTime(data["length"], 3)
        current_time = OpenMaya.MTime(data["time"], 3)
        OpenMayaAnim.MAnimControl.setMaxTime(length)
        OpenMayaAnim.MAnimControl.setCurrentTime(current_time)


# noinspection PyUnusedLocal
class DoF(Requests):
    def __init__(self, obj):
        super(DoF, self).__init__()
        self.start = None
        dag = OpenMaya.MFnDagNode(obj)
        # we need to get all of the attributes, we could have also used a container but I chose not to
        self.fp = dag.findPlug("focalPoint", False)
        self.w = dag.findPlug("width", False)
        self.n = dag.findPlug("far", False)
        self.f = dag.findPlug("near", False)
        self.old_width = dag.findPlug("oldWidth", False)
        self.old_fp = dag.findPlug("oldMid", False)
        self.fov = dag.findPlug("fov", False)

        self.last_fov = -1

        self.timeCallback = OpenMaya.MDGMessage.addForceUpdateCallback(self.time_update)
        self.attrCallback = OpenMaya.MNodeMessage.addAttributeChangedCallback(obj, self.set_attrs)

    def cleanup(self):
        OpenMaya.MMessage.removeCallback(self.attrCallback)
        OpenMaya.MMessage.removeCallback(self.timeCallback)

    def time_update(self, *args):
        context = OpenMaya.MDGContext(OpenMayaAnim.MAnimControl.currentTime())
        attr_dict = {
            "old_width": self.old_width.asFloat(context),
            "old_fp": self.old_fp.asFloat(context),
            "fp": self.fp.asFloat(context),
            "width": self.w.asFloat(context),
            "near": self.n.asFloat(context),
            "far": self.f.asFloat(context),
            "fov": self.fov.asFloat(context)
        }
        self.convert_dict(attr_dict)

    # set attrs
    def set_attrs(self, obj, plug, *args):
        # limit the callback rate a bit by making sure some time has passed since the last call
        if time.time() == self.start:
            return
        self.start = time.time()
        # create dict with attrs for readability
        attr_dict = {
            "old_width": self.old_width.asFloat(),
            "old_fp": self.old_fp.asFloat(),
            "fp": self.fp.asFloat(),
            "width": self.w.asFloat(),
            "near": self.n.asFloat(),
            "far": self.f.asFloat(),
            "fov": self.fov.asFloat()
        }
        # near = mid - width + (near - mid + last_width)
        near = attr_dict["fp"] - attr_dict["width"] + (attr_dict["near"] - attr_dict["fp"] + attr_dict["old_width"])
        # far = mid + width + (near - mid - last_width)
        far = attr_dict["fp"] + attr_dict["width"] + (attr_dict["far"] - attr_dict["fp"] - attr_dict["old_width"])

        # check which attr was changed to avoid overload and recursion
        if plug == self.fp:
            diff = attr_dict["fp"] - attr_dict["old_fp"]

            n = attr_dict["near"] + diff
            attr_dict["near"] = n

            f = attr_dict["far"] + diff
            attr_dict["far"] = f

            self.n.setFloat(n)
            self.f.setFloat(f)
            self.old_fp.setFloat(attr_dict["fp"])
        elif plug == self.w:
            self.n.setFloat(near)
            attr_dict["near"] = near

            self.f.setFloat(far)
            self.old_width.setFloat(attr_dict["width"])
        elif plug == self.fov:
            if plug.asFloat() == self.last_fov:
                return
            else:
                self.last_fov = plug.asFloat()
            print plug.asFloat()
            ReplayApiData.fov["fieldOfView"] = plug.asFloat()
            self.post("render", ReplayApiData.fov)
        self.convert_dict(attr_dict)

    def convert_dict(self, attr_dict):
        data = {
            "depthOfFieldFar": attr_dict["far"] * 10,
            "depthOfFieldMid": attr_dict["fp"] * 10,
            "depthOfFieldNear": attr_dict["near"] * 10,
            "fieldOfView": attr_dict["fov"]
        }
        self.post("render", data)
