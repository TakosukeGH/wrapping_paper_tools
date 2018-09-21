import bpy
import logging
import itertools
import math
import mathutils
import os
import bgl
from . exporter import SvgExporter
from bpy.props import PointerProperty, StringProperty, CollectionProperty, IntProperty, BoolProperty, IntVectorProperty, FloatVectorProperty, FloatProperty, EnumProperty, BoolVectorProperty
from bpy.app.translations import pgettext
from bpy.types import Panel, Operator, SpaceView3D, PropertyGroup

logger = logging.getLogger("wrapping_paper_tools")

# Properties
class SVGSceneProperties(PropertyGroup):
    height = IntProperty(name="Height", min=4, max=65536, default=3955)
    width = IntProperty(name="Width", min=4, max=65536, default=2825)
    scale = FloatProperty(name="Scale", min=0.00001, max=100000.0, step=1, default=100.0, precision=3)
    export_path = StringProperty(name="Export path", subtype='FILE_PATH', description="Export path", default="//sample.svg")
    set_group = StringProperty(name="Set group", description="Set group")
    draw_area = BoolProperty(default=False)
    slide = FloatProperty(name="Slide", step=10, default=0.1)
    slide_sub = FloatProperty(name="Slide", step=10, default=0.02)
    use_background = BoolProperty(name="Use backGround", default=False)
    background_color = FloatVectorProperty(name="Background Color", subtype='COLOR', size=4, min=0, max=1, default=[0.8, 0.8, 0.8, 0.8])
    script_is_executed = BoolProperty(default=False)
    lock_init_project = BoolProperty(default=False)
    use_location_noise = BoolProperty(name="Use location noise", default=False)
    distance = FloatProperty(name="Distance", min=0.0, soft_max=10, default=50.0, precision=3)
    location_noise = FloatProperty(name="Location noise", min=0.0, soft_max=10, default=0.0, precision=3)
    use_rotation_noise = BoolProperty(name="Use rotation noise", default=False)
    rotation_noise = FloatProperty(name="Rotation noise", min=0.0, soft_max=math.radians(20), default=0.0, precision=3, unit='ROTATION')
    random_seed = IntProperty(name="Seed", min=1, default=1)
    pattern_type = EnumProperty(
        name="Pattern type",
        items=(('0', "Square lattice", ""),('1', "Hexagonal lattice", ""))
    )

class SVGGroupProperties(PropertyGroup):
    export = BoolProperty(name="Export", default=False)

# Operator
class InitProjectOperator(bpy.types.Operator):
    bl_idname = "wpt.init_project_operator"
    bl_label = "Init Project"
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        logger.info("start")

        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete()

        self.screen_setting(context)
        self.scene_setting(context.scene)
        self.area_setting()

        context.scene.wpt_scene_properties.script_is_executed = True

        logger.info("end")

        return {'FINISHED'}

    def screen_setting(self, context):
        screens = bpy.data.screens

        screen_names = ["3D View Full", "Game Logic", "Motion Tracking", "Video Editing"]

        for screen_name in screen_names:
            if screen_name in screens:
                bpy.ops.screen.delete({'screen': screens[screen_name]})

        context.window.screen = screens['Default']

    def scene_setting(self, scene):
        scene.render.engine = 'CYCLES'

    def area_setting(self):
        for screen in bpy.data.screens:
            for area in screen.areas:
                if area.type == 'VIEW_3D':
                    override = bpy.context.copy()
                    override["window"] = bpy.context.window
                    override["screen"] = screen
                    override["area"] = area
                    bpy.ops.view3d.view_persportho(override)
                    bpy.ops.view3d.viewnumpad(override, type='TOP')

                    logger.debug("area_setting in:" + screen.name)

                    for space in area.spaces:
                        space.use_occlude_geometry = False
                        # space.lens = 50

# UI
class WPTToolPanel(Panel):
    bl_idname = "OBJECT_PT_wpt"
    bl_label = "Wrapping Paper Tools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'TOOLS'
    bl_category = 'WPT'

    def draw(self, context):
        wpt_scene_properties = context.scene.wpt_scene_properties

        if not wpt_scene_properties.script_is_executed:
            row = self.layout.row()
            row.scale_y = 2.0
            row.operator(InitProjectOperator.bl_idname, text=pgettext(InitProjectOperator.bl_label), icon='LOAD_FACTORY')
            return

        layout = self.layout

        # オブジェクト操作系
        row = layout.row()
        row.operator(AddCurveTool.bl_idname, icon='CURVE_BEZCIRCLE')

        col = layout.column(align=True)
        row = col.row(align=True)
        row.operator(UpObject.bl_idname, icon='TRIA_UP')
        row.operator(DownObject.bl_idname, icon='TRIA_DOWN')
        col.prop(wpt_scene_properties, "slide")
        row = col.row(align=True)
        row.operator(UpObjectSub.bl_idname, icon='TRIA_UP_BAR')
        row.operator(DownObjectSub.bl_idname, icon='TRIA_DOWN_BAR')
        col.prop(wpt_scene_properties, "slide_sub")
        col.operator(ResetObject.bl_idname, icon='X')

        if context.object is not None:
            obj = context.object
            if obj.type == 'CURVE':
                row = layout.row()
                row.prop(obj.data, "resolution_u")
                if len(obj.data.materials) > 0:
                    mat = obj.data.materials[0]
                    row = layout.row()
                    row.template_ID(obj, "active_material", new="material.new")
                    col = layout.column(align=True)
                    # col.label("Viewport Color:")
                    col.prop(mat, "diffuse_color", text="")
                    col.prop(mat, "alpha")

        # グループ系
        layout.row().separator()

        if context.object is not None:
            for group in bpy.data.groups:
                group_objects = group.objects
                if context.object.name in group.objects and context.object in group_objects[:]:
                    row = layout.row()
                    row.label("Group")
                    row = layout.row()
                    row.prop(group, "name", text="")

                    wpt_group_properties = group.wpt_group_properties
                    row = layout.row()
                    row.prop(wpt_group_properties, "export")

        # row = layout.row()
        # row.prop_search(wpt_scene_properties, "set_group", bpy.data, "groups", text="")

        # 出力系
        layout.row().separator()

        row = layout.row()
        row.label("Output")
        row = layout.row()
        row.prop(wpt_scene_properties, "export_path", text="")

        col = layout.column(align=True)
        row = col.row(align=True)
        row.scale_y = 2.0
        row.operator(SvgExporter.bl_idname, icon='EXPORT')
        row = col.row(align=True)
        row.operator(OpenSvg.bl_idname, icon='WORLD')

        # 枠・背景
        layout.row().separator()

        row = layout.row()
        row.label("Background")

        row = layout.row()
        if wpt_scene_properties.draw_area is False:
            icon = 'PLAY'
            txt = 'Display border'
        else:
            icon = "PAUSE"
            txt = 'Hide border'

        row.operator("wpt.runopenglbutton", text=txt, icon=icon)

        # layout.prop(wpt_scene_properties, "property_type", expand=True)
        col = layout.column(align=True)
        col.prop(wpt_scene_properties, "height")
        col.prop(wpt_scene_properties, "width")
        col.prop(wpt_scene_properties, "scale")

        row = layout.row()
        row.prop(wpt_scene_properties, "use_background", text="Use background")

        row = layout.row()
        if wpt_scene_properties.use_background:
            row.prop(wpt_scene_properties, "background_color", text="")

        row = layout.row()
        row.prop(wpt_scene_properties, "distance")
        row = layout.row()
        row.label("Pattern")
        row = layout.row()
        row.prop(wpt_scene_properties, "pattern_type", text="")

        row = layout.row()
        row.prop(wpt_scene_properties, "use_location_noise")

        if wpt_scene_properties.use_location_noise:
            row = layout.row()
            row.prop(wpt_scene_properties, "location_noise")

        row = layout.row()
        row.prop(wpt_scene_properties, "use_rotation_noise")

        if wpt_scene_properties.use_rotation_noise:
            row = layout.row()
            row.prop(wpt_scene_properties, "rotation_noise")

        row = layout.row()
        row.prop(wpt_scene_properties, "random_seed")

        layout.row().separator()


class OBJECT_PT_wpt_groups(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"
    bl_label = "WPT Groups"

    def draw(self, context):
        layout = self.layout
        obj = context.object
        for group in bpy.data.groups:
            group_objects = group.objects
            if obj.name in group.objects and obj in group_objects[:]:
                layout.prop(group, "name", text="")
                wpt_group_properties = group.wpt_group_properties
                layout.prop(wpt_group_properties, "export")

# op
class AddCurveTool(Operator):
    bl_idname = "wpt.addcurve"
    bl_label = "Add curve"

    def invoke(self, context, event):
        loc_z = 0.0
        use_group = False
        group = None
        if len(context.selected_objects) > 0:
            loc_z = context.object.location[2] + context.scene.wpt_scene_properties.slide
            for g in bpy.data.groups:
                if context.object.name in g.objects:
                    group = g
                    break

        loc=(0.0, 0.0, loc_z)

        if group is None:
            group = bpy.data.groups.new("Group")

        bpy.ops.curve.primitive_bezier_circle_add(location=loc)
        obj = context.object
        group.objects.link(obj)
        group.wpt_group_properties.export = True

        obj.lock_location = (True, True, True)
        obj.lock_rotation = (True, True, True)
        obj.lock_scale = (True, True, True)

        curve = obj.data

        curve.dimensions = '2D'
        curve.resolution_u = 5

        mat = bpy.data.materials.new(name="wpt_material")
        mat.diffuse_color = (1.0, 1.0, 1.0)
        curve.materials.append(mat)

        return {'FINISHED'}

class UpObject(Operator):
    bl_idname = "wpt.upobject"
    bl_label = "Up"

    def invoke(self, context, event):
        slide = context.scene.wpt_scene_properties.slide
        for obj in context.selected_objects:
            obj.location[2] += slide

        return {'FINISHED'}

class DownObject(Operator):
    bl_idname = "wpt.downobject"
    bl_label = "Down"

    def invoke(self, context, event):
        slide = context.scene.wpt_scene_properties.slide
        for obj in context.selected_objects:
            obj.location[2] -= slide

        return {'FINISHED'}

class UpObjectSub(Operator):
    bl_idname = "wpt.upobject_sub"
    bl_label = "Up"

    def invoke(self, context, event):
        slide = context.scene.wpt_scene_properties.slide_sub
        for obj in context.selected_objects:
            obj.location[2] += slide

        return {'FINISHED'}

class DownObjectSub(Operator):
    bl_idname = "wpt.downobject_sub"
    bl_label = "Down"

    def invoke(self, context, event):
        slide = context.scene.wpt_scene_properties.slide_sub
        for obj in context.selected_objects:
            obj.location[2] -= slide

        return {'FINISHED'}

class ResetObject(Operator):
    bl_idname = "wpt.resetobject"
    bl_label = "Reset"

    def invoke(self, context, event):
        for obj in context.selected_objects:
            obj.location[2] = 0.0

        return {'FINISHED'}

class OpenSvg(Operator):
    bl_idname = "wpt.opensvg"
    bl_label = "Open SVG"

    def invoke(self, context, event):
        file_path = bpy.path.abspath(context.scene.wpt_scene_properties.export_path)
        try: bpy.ops.wm.url_open(url=file_path)
        except: pass
        return{'FINISHED'}

        return {'FINISHED'}

class RunHintDisplayButton(Operator):
    bl_idname = "wpt.runopenglbutton"
    bl_label = "Display hint data manager"

    _handle_3d = None

    def invoke(self, context, event):
        if context.scene.wpt_scene_properties.draw_area is False:
            logger.debug("check 1")
            if context.area.type == 'VIEW_3D':
                args = (self, context)
                RunHintDisplayButton._handle_3d = bpy.types.SpaceView3D.draw_handler_add(draw_callback_3d, args, 'WINDOW', 'POST_VIEW')
                context.scene.wpt_scene_properties.draw_area = True
                context.area.tag_redraw()
                return {'FINISHED'}
            else:
                self.report({'WARNING'}, "View3D not found, cannot run operator")
                return {'CANCELLED'}
        else:
            logger.debug("check 2")
            logger.debug(context.scene.wpt_scene_properties.draw_area)
            if RunHintDisplayButton._handle_3d is not None:
                logger.debug(type(RunHintDisplayButton._handle_3d))
                bpy.types.SpaceView3D.draw_handler_remove(RunHintDisplayButton._handle_3d, 'WINDOW')
                context.scene.wpt_scene_properties.draw_area = False
                context.area.tag_redraw()
            else:
                context.scene.wpt_scene_properties.draw_area = False
            return {'FINISHED'}

def draw_callback_3d(self, context):
    bgl.glEnable(bgl.GL_BLEND)

    height = context.scene.wpt_scene_properties.height
    width = context.scene.wpt_scene_properties.width
    scale = context.scene.wpt_scene_properties.scale

    draw_line_3d((-width/2/scale, height/2/scale, 0.0), (width/2/scale, height/2/scale, 0.0))
    draw_line_3d((width/2/scale, height/2/scale, 0.0), (width/2/scale, -height/2/scale, 0.0))
    draw_line_3d((width/2/scale, -height/2/scale, 0.0), (-width/2/scale, -height/2/scale, 0.0))
    draw_line_3d((-width/2/scale, -height/2/scale, 0.0), (-width/2/scale, height/2/scale, 0.0))

    # restore opengl defaults
    bgl.glLineWidth(1)
    bgl.glDisable(bgl.GL_BLEND)
    bgl.glColor4f(0.0, 0.0, 0.0, 1.0)

def draw_line_3d(start, end, width=1):
    bgl.glLineWidth(width)
    bgl.glColor4f(1.0, 1.0, 0.0, 0.5)
    bgl.glBegin(bgl.GL_LINES)
    bgl.glVertex3f(*start)
    bgl.glVertex3f(*end)
    bgl.glEnd()

translations = {
    "ja_JP": {
        ("*", "Base Settings"): "基本設定",
        ("*", "Export SVG"): "Export SVG",
        ("*", "Use background"): "背景色を使用",
        ("*", "Use location noise"): "位置ノイズを使用",
        ("*", "Location noise"): "位置ノイズ",
        ("*", "Use rotation noise"): "回転ノイズを使用",
        ("*", "Rotation noise"): "回転ノイズ",
        ("*", "Square lattice"): "正方格子",
        ("*", "Hexagonal lattice"): "六角格子",
    }
}

def register():
    bpy.types.Scene.wpt_scene_properties = PointerProperty(type=SVGSceneProperties)
    bpy.types.Group.wpt_group_properties = PointerProperty(type=SVGGroupProperties)

    bpy.app.translations.register(__name__, translations)

def unregister():
    bpy.app.translations.unregister(__name__)
    del bpy.types.Scene.wpt_scene_properties
