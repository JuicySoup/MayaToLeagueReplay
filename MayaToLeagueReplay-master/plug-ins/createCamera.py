from maya.api import OpenMaya


def maya_useNewAPI():
    pass


kPluginCmdName = "leagueCam"


# noinspection PyMethodOverriding,PyAttributeOutsideInit
class LeagueCam(OpenMaya.MPxCommand):

    def __init__(self):
        super(LeagueCam, self).__init__()
        self.defaults = {
            "dofSep": "DoF",
            "focalPoint": 200,
            "width": 200,
            "near": 400,
            "far": 0,
            "oldWidth": 200,
            "oldMid": 200,
            "fov": 40
        }

    def doIt(self, args):
        self.redoIt()

    def redoIt(self):
        dag_node = OpenMaya.MFnDagNode()
        self.transform = dag_node.create("transform", "camera")
        name = OpenMaya.MFnDependencyNode(self.transform).name()
        dag_node.create("camera", "{}Shape".format(name), self.transform)

        attr_list = [["dofSep", "dS"], ["focalPoint", "fp"], ["width", "w"], ["near", "n"], ["far", "f"],
                     ["oldWidth", "ow"], ["oldMid", "om"], ["fovSep", "fS"], ["fov", "fov"]]

        for attrs in attr_list:
            attr = self.create_attr(attrs)
            mdg = OpenMaya.MDGModifier()
            mdg.addAttribute(self.transform, attr)
            mdg.doIt()

        dag = OpenMaya.MFnDagNode(self.transform)
        dag.findPlug("dofSep", False).isLocked = True
        dag.findPlug("fovSep", False).isLocked = True

        OpenMaya.MGlobal.selectByName(name, OpenMaya.MGlobal.kReplaceList)

    def create_attr(self, attrs):
        if attrs[0] == "dofSep" or attrs[0] == "fovSep":
            field_dict = {
                "dofSep": "DoF",
                "fovSep": "FoV"
            }
            fn = OpenMaya.MFnEnumAttribute()
            attr = fn.create(attrs[0], attrs[1], 0)
            fn.addField(field_dict[attrs[0]], 0)
            fn.keyable = True
            fn.setNiceNameOverride("----------")
            return attr
        fn = OpenMaya.MFnNumericAttribute()
        attr = fn.create(attrs[0], attrs[1], OpenMaya.MFnNumericData.kFloat, self.defaults[attrs[0]])
        if attrs[0] == "fov":
            fn.setMax(180)
            fn.setNiceNameOverride("FoV")
        else:
            fn.setMax(1000)
        fn.setMin(0)
        if attrs[0] == "oldWidth" or attrs[0] == "oldMid":
            fn.keyable = False
        else:
            fn.keyable = True
        return attr

    def undoIt(self):
        OpenMaya.MGlobal.deleteNode(self.transform)

    def isUndoable(self):
        return True


def cmdCreator():
    return LeagueCam()


def initializePlugin(mobject):
    mplugin = OpenMaya.MFnPlugin(mobject)
    try:
        mplugin.registerCommand(kPluginCmdName, cmdCreator)
    except:
        OpenMaya.MGlobal.displayError("Failed to register command: " + kPluginCmdName)


def uninitializePlugin(mobject):
    mplugin = OpenMaya.MFnPlugin(mobject)
    try:
        mplugin.deregisterCommand(kPluginCmdName)
    except:
        OpenMaya.MGlobal.displayError("Failed to deregister command: " + kPluginCmdName)
