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
    script_is_executed: BoolProperty(default=False)
    lock_init_project: BoolProperty(default=False)
    # オブジェクト系
    slide: FloatProperty(name="Slide", step=10, default=0.1)
    slide_sub: FloatProperty(name="Slide", step=10, default=0.02)
    # 出力系
    export_path: StringProperty(name="Export path", subtype='FILE_PATH', description="Export path", default="//sample.svg")
    # 枠・背景
    draw_area: BoolProperty(default=False)
    height: IntProperty(name="Height", min=4, max=65536, default=3955)
    width: IntProperty(name="Width", min=4, max=65536, default=2825)
    scale: FloatProperty(name="Scale", min=0.00001, max=100000.0, step=1, default=100.0, precision=3)
    use_background: BoolProperty(name="Use backGround", default=False)
    use_stripe_background: BoolProperty(name="Use stripe backGround", default=False)
    background_color: FloatVectorProperty(name="Background Color", subtype='COLOR', size=4, min=0, max=1, default=[0.0, 0.0, 0.0, 1.0])
    # パターン系
    use_location_noise: BoolProperty(name="Use location noise", default=False)
    distance_x: FloatProperty(name="Distance X", min=0.0, default=500.0, precision=1)
    distance_y: FloatProperty(name="Distance Y", min=0.0, default=500.0, precision=1)
    offset_y: FloatProperty(name="Offset Y", min=0.0, default=0.0, precision=1)
    location_noise: FloatProperty(name="Location noise", min=0.0, default=0.0, precision=3)
    use_rotation_noise: BoolProperty(name="Use rotation noise", default=False)
    rotation_noise: FloatProperty(name="Rotation noise", min=0.0, soft_max=math.radians(20), default=0.0, precision=3, unit='ROTATION')
    random_seed: IntProperty(name="Seed", min=1, default=1)
    pattern_type: EnumProperty(
        name="Pattern type",
        items=(('0', "Square lattice", ""),('1', "Hexagonal lattice", ""),('2', "Yagasuri", ""),('3', "Circle packing", "")),
        default='1'
    )
    yagasuri_turn: BoolProperty(name="Turn", default=False)
    collection_index_offset: IntProperty(name="Group index offset", min=0, default=0)

class SVGCollectionProperties(PropertyGroup):
    export: BoolProperty(name="Export", default=False)

# Operator
class InitProjectOperator(Operator):
    bl_idname = "wpt.init_project_operator"
    bl_label = "Init Project"
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        logger.info("start")

        logger.info("check4")

        bpy.ops.object.select_all(action='SELECT')
        if len(bpy.context.selected_objects) > 0:
            bpy.ops.object.delete()

        self.area_setting()

        context.scene.wpt_scene_properties.script_is_executed = True

        logger.info("end")

        return {'FINISHED'}

    def area_setting(self):
        for screen in bpy.data.screens:
            for area in screen.areas:
                if area.ui_type == 'VIEW_3D':
                    override = bpy.context.copy()
                    override["window"] = bpy.context.window
                    override["screen"] = screen
                    override["area"] = area
                    bpy.ops.view3d.view_persportho(override)
                    bpy.ops.view3d.view_axis(override, type='TOP')

                    logger.debug("area_setting in:" + screen.name)

# UI
class VIEW3D_PT_tools_wpt(Panel):
    bl_idname = "OBJECT_PT_wpt"
    bl_label = "Wrapping Paper Tools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'WPT'

    def draw(self, context):
        wpt_scene_properties = context.scene.wpt_scene_properties

        if not wpt_scene_properties.script_is_executed:
            row = self.layout.row()
            row.scale_y = 2.0
            row.operator(InitProjectOperator.bl_idname, text=pgettext(InitProjectOperator.bl_label), icon='FILE_BLEND')
            return

        layout = self.layout

        # オブジェクト操作系
        row = layout.row()
        row.operator(AddCurveTool.bl_idname, icon='CURVE_BEZCIRCLE')

        col = layout.column(align=True)
        if context.object is not None:
            obj = context.object
            col.prop(obj, "location", index=2)
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
                    # col.label(text="Viewport Color:")
                    col.prop(mat, "diffuse_color", text="")

        col = layout.column(align=True)
        col.operator("object.select_grouped").type = 'COLLECTION'
        col.operator(UnrockObject.bl_idname, icon='UNLOCKED')
        col.operator(RockObject.bl_idname, icon='LOCKED')
        col.operator(ApplyObject.bl_idname, icon='FILE_TICK')

        self.draw_collection(context)

        # 出力系
        layout.row().separator()

        row = layout.row()
        row.label(text="Output")
        row = layout.row()
        row.prop(wpt_scene_properties, "export_path", text="")

        if not bpy.data.is_saved:
            row = layout.row()
            row.alert = True
            row.label(text="File has not been saved.")

        col = layout.column(align=True)
        row = col.row(align=True)
        row.scale_y = 2.0
        row.operator(SvgExporter.bl_idname, icon='EXPORT')
        if not bpy.data.is_saved:
            row.enabled = False
        row = col.row(align=True)
        row.operator(OpenSvg.bl_idname, icon='WORLD')

        # 枠・背景
        layout.row().separator()

        row = layout.row()
        row.label(text="Background")

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
        row.prop(wpt_scene_properties, "use_stripe_background", text="Use stripe background")

        layout.row().separator()

        self.draw_pattern(context)

    def draw_collection(self, context):
        layout = self.layout
        layout.row().separator()

        if context.object is not None:
            for collection in bpy.data.collections:
                if context.object.name in collection.objects:
                # if context.object.name in collection.objects and context.object in collection.objects[:]:
                    row = layout.row()
                    row.label(text="Group")
                    row = layout.row()
                    row.prop(collection, "name", text="")

                    wpt_collection_properties = collection.wpt_collection_properties
                    row = layout.row()
                    row.prop(wpt_collection_properties, "export")

        col = layout.column(align=True)
        row = col.row(align=True)
        row.operator(SelectCollection.bl_idname, icon='CHECKBOX_HLT')
        row = col.row(align=True)
        row.operator(DeselectCollection.bl_idname, icon='CHECKBOX_DEHLT')

    def draw_pattern(self, context):
        wpt_scene_properties = context.scene.wpt_scene_properties
        layout = self.layout

        row = layout.row()
        row.label(text="Pattern")
        row = layout.row()
        row.prop(wpt_scene_properties, "pattern_type", text="")

        pattern = wpt_scene_properties.pattern_type
        if pattern == "0": # Square lattice
            col = layout.column(align=True)
            row = col.row(align=True)
            row.prop(wpt_scene_properties, "distance_x")
            row = col.row(align=True)
            row.prop(wpt_scene_properties, "distance_y")
        elif pattern == "1" or pattern == "2": # Hexagonal lattice
            col = layout.column(align=True)
            row = col.row(align=True)
            row.prop(wpt_scene_properties, "distance_x")
            row = col.row(align=True)
            row.prop(wpt_scene_properties, "offset_y")
        elif pattern == "1" or pattern == "2": # Hexagonal lattice
            col = layout.column(align=True)
            row = col.row(align=True)
            row.prop(wpt_scene_properties, "distance_x")
            row = col.row(align=True)
            row.prop(wpt_scene_properties, "distance_y")
            row = col.row(align=True)
            row.prop(wpt_scene_properties, "offset_y")

        if pattern == "0" or pattern == "1":
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

        elif pattern == "2": # Yagasuri
            row = layout.row()
            row.prop(wpt_scene_properties, "yagasuri_turn")

        elif pattern == "3": # Circle packing
            row = layout.row()
            row.prop(wpt_scene_properties, "use_rotation_noise")

            if wpt_scene_properties.use_rotation_noise:
                col = layout.column(align=True)
                row = col.row(align=True)
                row.prop(wpt_scene_properties, "rotation_noise")
                row = col.row(align=True)
                row.prop(wpt_scene_properties, "random_seed")

            col = layout.column(align=True)
            row = col.row(align=True)
            row.prop(wpt_scene_properties, "collection_index_offset")

class OBJECT_PT_wpt_collections(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"
    bl_label = "WPT Groups"

    def draw(self, context):
        layout = self.layout
        obj = context.object
        for collection in bpy.data.collections:
            collection_objects = collection.objects
            if obj.name in collection.objects and obj in collection_objects[:]:
                layout.prop(collection, "name", text="")
                wpt_collection_properties = collection.wpt_collection_properties
                layout.prop(wpt_collection_properties, "export")

# op
class AddCurveTool(Operator):
    bl_idname = "wpt.addcurve"
    bl_label = "Add curve"

    def invoke(self, context, event):
        if context.object is not None:
            bpy.ops.object.mode_set(mode='OBJECT')

        loc_z = 0.0
        collection = None

        # 選択中のオブジェクトのZ位置とコレクションを取得
        if len(bpy.data.objects) <= 0:
            collection = context.view_layer.active_layer_collection.collection
        elif len(context.selected_objects) > 0:
            loc_z = context.object.location.z + context.scene.wpt_scene_properties.slide
            collections = context.object.users_collection
            if len(collections) > 0:
                collection = collections[0]

        loc = (0.0, 0.0, loc_z)

        if collection is None:
            collection = bpy.data.collections.new("Collection")
            context.scene.collection.children.link(collection)

        collection.wpt_collection_properties.export = True
        layer_collection = context.view_layer.layer_collection.children[collection.name]
        context.view_layer.active_layer_collection = layer_collection
        bpy.ops.curve.primitive_bezier_circle_add(location=loc)
        obj = context.object

        obj.lock_location = (True, True, True)
        obj.lock_rotation = (True, True, True)
        obj.lock_scale = (True, True, True)

        curve = obj.data
        curve.dimensions = '2D'
        curve.resolution_u = 5
        curve.fill_mode = 'FRONT'

        mat = bpy.data.materials.new(name="wpt_material")
        mat.diffuse_color = (1.0, 1.0, 1.0, 1.0)
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

class UnrockObject(Operator):
    bl_idname = "wpt.unrockobject"
    bl_label = "Unrock"

    def invoke(self, context, event):
        for obj in context.selected_objects:
            obj.lock_location[0] = False
            obj.lock_location[1] = False
            obj.lock_scale[0] = False
            obj.lock_scale[1] = False

        return {'FINISHED'}

class RockObject(Operator):
    bl_idname = "wpt.rockobject"
    bl_label = "Rock"

    def invoke(self, context, event):
        for obj in context.selected_objects:
            obj.lock_location[0] = True
            obj.lock_location[1] = True
            obj.lock_scale[0] = True
            obj.lock_scale[1] = True

        return {'FINISHED'}

class ApplyObject(Operator):
    bl_idname = "wpt.applyobject"
    bl_label = "Apply"

    def invoke(self, context, event):
        bpy.ops.view3d.view_all(center=True)
        bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

        return {'FINISHED'}

class SelectCollection(Operator):
    bl_idname = "wpt.selectcollection"
    bl_label = "Select All Collections"

    def invoke(self, context, event):
        for collection in bpy.data.collections:
            collection.wpt_collection_properties.export = True

        return {'FINISHED'}

class DeselectCollection(Operator):
    bl_idname = "wpt.deselectcollection"
    bl_label = "Deselect All Collections"

    def invoke(self, context, event):
        for collection in bpy.data.collections:
            collection.wpt_collection_properties.export = False

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
        ("*", "Use stripe background"): "縞模様背景を使用",
        ("*", "Use location noise"): "位置ノイズを使用",
        ("*", "Location noise"): "位置ノイズ",
        ("*", "Use rotation noise"): "回転ノイズを使用",
        ("*", "Rotation noise"): "回転ノイズ",
        ("*", "Square lattice"): "正方格子",
        ("*", "Hexagonal lattice"): "六角格子",
        ("*", "Circle packing"): "円充填",
        ("*", "Distance X"): "距離 X",
        ("*", "Distance Y"): "距離 Y",
        ("*", "Offset Y"): "オフセット Y",
        ("*", "Yagasuri"): "矢絣",
        ("*", "Select All Collections"): "全てのコレクションを選択",
        ("*", "Deselect All Collections"): "全てのコレクションを解除",
    }
}

classes = (
    SVGSceneProperties,
    SVGCollectionProperties,
    InitProjectOperator,
    VIEW3D_PT_tools_wpt,
    OBJECT_PT_wpt_collections,
    AddCurveTool,
    UpObject,
    DownObject,
    UpObjectSub,
    DownObjectSub,
    ResetObject,
    UnrockObject,
    RockObject,
    ApplyObject,
    SelectCollection,
    DeselectCollection,
    OpenSvg,
    RunHintDisplayButton,
)

def register():
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)

    bpy.types.Scene.wpt_scene_properties = PointerProperty(type=SVGSceneProperties)
    bpy.types.Collection.wpt_collection_properties = PointerProperty(type=SVGCollectionProperties)

    bpy.app.translations.register(__name__, translations)

def unregister():
    bpy.app.translations.unregister(__name__)
    del bpy.types.Collection.wpt_collection_properties
    del bpy.types.Scene.wpt_scene_properties

    from bpy.utils import unregister_class
    for cls in classes:
        unregister_class(cls)

