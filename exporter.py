import bpy
import colorsys
import csv
import io
import logging
import math
import mathutils
import operator
import random
import svgwrite

logger = logging.getLogger("wrapping_paper_tools")

class SvgExporter(bpy.types.Operator):
    bl_idname = "wpt.exporter"
    bl_label = "Export Wrapping Paper"
    location_matrix = mathutils.Matrix((
        [1.0, 0.0, 0.0],
        [0.0, -1.0, 0.0],
        [0.0, 0.0, 1.0]))

    def __init__(self):
        logger.info("start")

        self.collections = []
        self.objs = []
        self.points = []
        self.points_c = []
        self.uses = []
        self.duplicate_objs = []

        self.scale = 0.0

        logger.info("end")

    def invoke(self, context, event):
        logger.info("start")

        wpt_scene_properties = context.scene.wpt_scene_properties
        export_path = bpy.path.abspath(wpt_scene_properties.export_path)
        width = wpt_scene_properties.width
        height = wpt_scene_properties.height
        self.scale = wpt_scene_properties.scale

        # self.svg = svgwrite.Drawing(filename=export_path, size=(width,height), profile='tiny')
        self.svg = svgwrite.Drawing(filename=export_path, size=(width,height))
        self.svg.viewbox(minx=-width/2, miny=-height/2, width=width, height=height)

        if wpt_scene_properties.use_background:
            background_color = wpt_scene_properties.background_color
            rect = self.svg.rect(insert=(-width/2, -height/2), size=('100%', '100%'), rx=None, ry=None, fill=self.get_color(background_color), opacity=background_color[3])
            self.svg.add(rect)

        if wpt_scene_properties.use_stripe_background:
            self.add_stripe(width, height)

        self.get_objects()
        self.add_defs()
        self.create_points(width, height)
        self.create_uses()

        logger.debug("save: start")
        self.svg.save()
        logger.debug("save: end")

        logger.info("end")

        return {'FINISHED'}

    def add_stripe(self, width, height):
        for row in bpy.data.texts["stripe_data.csv"].lines:
            if not row.body:
                continue

            point, r, g, b = row.body.split(',')
            # logger.debug("point: " + str(point))

            svg_color = svgwrite.rgb(float(r),float(g),float(b))
            rect = self.svg.rect(insert=(float(point), -height/2.0), size=('100%', '100%'), rx=None, ry=None, fill=svg_color, opacity=1.0)
            self.svg.add(rect)

    def get_objects(self):
        for collection in bpy.data.collections:
            if not collection.wpt_collection_properties.export:
                continue

            if len(collection.objects) <= 0:
                continue

            self.collections.append(collection)

        for obj in bpy.data.objects:
            if obj.hide_viewport:
                continue

            if obj.type != 'CURVE':
                continue

            curve = obj.data

            if curve.dimensions != '2D':
                logger.info("This curve is not 2D: " + str(obj.name))
                continue

            if len(curve.materials) <= 0:
                logger.info("This data has no material: " + str(obj.name))
                continue

            material = curve.materials[0]

            if material is None:
                logger.info("This material slot has no material: " + str(obj.name))
                return

            self.objs.append(obj)

    def add_defs(self):
        for collection in self.collections:
            svg_group = self.svg.g(id=collection.name)

            # z位置が小さい順にsvgを定義していく
            for obj in sorted(collection.objects, key=lambda obj: obj.location.z):
                self.add_curve_data(obj, svg_group)

            self.svg.defs.add(svg_group)

            logger.debug("add group: " + collection.name)

    def add_curve_data(self, obj, group):
        # logger.debug("add path: " + str(obj.name))
        color, alpha = self.get_diffuse_color(obj)
        curve = obj.data
        matrix_world = obj.matrix_world
        scale = bpy.context.scene.wpt_scene_properties.scale

        for spline in curve.splines:
            if spline.type != 'BEZIER':
                logger.info("Spline type is not BEZIER")
                continue

            # ループしているかの判定。使うかどうか検討中。
            is_loop = spline.use_cyclic_u

            svg_path = SVGPath(spline, matrix_world, scale)

            # self.svg.add(self.svg.path(d=svg_path.d, fill=color, opacity=alpha, stroke=color))
            group.add(self.svg.path(d=svg_path.d, fill=color, opacity=alpha, stroke=color))

    def get_diffuse_color(self, obj):
        material = obj.data.materials[0]
        diffuse_color = material.diffuse_color
        return self.get_color(diffuse_color), diffuse_color[3]

    def get_color(self, color):
        gamma = 2.2
        r = 255 * pow(color[0], 1/gamma)
        g = 255 * pow(color[1], 1/gamma)
        b = 255 * pow(color[2], 1/gamma)
        return svgwrite.rgb(r,g,b)

    def create_points(self, width, height):
        wpt_scene_properties = bpy.context.scene.wpt_scene_properties
        random.seed(wpt_scene_properties.random_seed)
        pattern = wpt_scene_properties.pattern_type
        noise_limit = wpt_scene_properties.location_noise
        use_location_noise = wpt_scene_properties.use_location_noise
        noise_x = 0
        noise_y = 0

        if pattern == "0": # Square lattice
            distance_x = wpt_scene_properties.distance_x
            distance_y = wpt_scene_properties.distance_y

            count_x = int(width/2) // int(distance_x)
            count_y = int(height/2) // int(distance_y)
            for x in range(-count_x, count_x + 1, 1):
                for y in range(-count_y, count_y + 1, 1):
                    if use_location_noise:
                        noise_x = random.uniform(-noise_limit, noise_limit)
                        noise_y = random.uniform(-noise_limit, noise_limit)
                    point = mathutils.Vector((x * distance_x + noise_x, y * distance_y + noise_y))
                    self.points.append(point)

        elif pattern == "1": # Hexagonal lattice
            distance_x = wpt_scene_properties.distance_x
            offset_y = wpt_scene_properties.offset_y

            count_x = int(width/2) // int(distance_x)
            distance_y = distance_x*math.sqrt(3)/2 + offset_y
            count_y = int((height/2) // distance_y)

            for y in range(-count_y, count_y + 1, 1):
                if y % 2 == 0:
                    for x in range(-count_x, count_x + 1, 1):
                        if use_location_noise:
                            noise_x = random.uniform(-noise_limit, noise_limit)
                            noise_y = random.uniform(-noise_limit, noise_limit)
                        point = mathutils.Vector((x * distance_x + noise_x, y * distance_y + noise_y))
                        self.points.append(point)
                else:
                    for x in range(-count_x - 1, count_x + 1, 1):
                        if use_location_noise:
                            noise_x = random.uniform(-noise_limit, noise_limit)
                            noise_y = random.uniform(-noise_limit, noise_limit)
                        point = mathutils.Vector(((x + 1/2) * distance_x  + noise_x, y * distance_y + noise_y))
                        self.points.append(point)

        elif pattern == "2": # Yagasuri
            scale = wpt_scene_properties.scale
            distance_x = wpt_scene_properties.distance_x
            distance_y = wpt_scene_properties.distance_y
            offset_y = wpt_scene_properties.offset_y

            count_x = int(width/2) // int(distance_x)
            count_y = int(height/2) // int(distance_y)

            for y in range(-count_y - 1, count_y + 1, 1):
                for x in range(-count_x, count_x + 1, 1):
                    point = mathutils.Vector((x * distance_x, y * distance_y))
                    if wpt_scene_properties.yagasuri_turn:
                        self.points_c.append(SVGPoint(point,0,180))
                    else:
                        self.points_c.append(SVGPoint(point,0))

                for x in range(-count_x - 1, count_x + 1, 1):
                    point = mathutils.Vector(((x + 1/2) * distance_x, y * distance_y - offset_y))
                    self.points_c.append(SVGPoint(point,1))

        elif pattern == "3": # Circle packing
            # with open('circles_data.csv', 'r') as f:
                # reader = csv.reader(f)
            for row in bpy.data.texts["circles_data.csv"].lines:
                if not row.body:
                    continue

                row_array = row.body.split(',')
                self.points.append(SVGPoint(mathutils.Vector((float(row_array[0]), float(row_array[1]))), radius=float(row_array[2])))

    def create_uses(self):
        logger.info("start")

        if len(self.collections) <= 0:
            return

        wpt_scene_properties = bpy.context.scene.wpt_scene_properties
        use_rotation_noise = wpt_scene_properties.use_rotation_noise
        noise_limit_degrees = wpt_scene_properties.rotation_noise

        pattern = wpt_scene_properties.pattern_type
        if pattern == "0" or pattern == "1": # Square lattice, Hexagonal lattice
            for point in self.points:
                collection = random.choice(self.collections)

                use = self.svg.use(self.svg.symbol(id=collection.name), insert=(point.x, -point.y), size=(100,100))

                if use_rotation_noise:
                    noise_rotation_degrees = random.uniform(-noise_limit_degrees, noise_limit_degrees)
                    use.rotate(angle = math.degrees(noise_rotation_degrees), center = (point.x, -point.y))

                self.svg.add(use)

        elif pattern == "2":
            for point in self.points_c:
                collection = self.collections[point.collection]

                use = self.svg.use(self.svg.symbol(id=collection.name), insert=(point.location.x, -point.location.y), size=(100,100))

                if point.rotate != 0:
                    use.rotate(angle = point.rotate, center = (point.location.x, -point.location.y))

                self.svg.add(use)

        elif pattern == "3": # Circle packing
            logger.info("start create uses for Circle packing")
            transform_tmpl = "scale({0},{1}) translate({2},{3})"
            collection_index_offset = wpt_scene_properties.collection_index_offset
            for index, point in enumerate(self.points):
                collection = self.collections[(index + collection_index_offset) % len(self.collections)]

                # logger.info(point.radius)

                scale = point.radius * self.scale * 0.0001
                translate_x = -point.location.x * (1 - 1/scale)
                translate_y = point.location.y * (1 - 1/scale)
                transform = transform_tmpl.format(scale,scale,translate_x,translate_y)
                use = self.svg.use(self.svg.symbol(id=collection.name), insert=(point.location.x, -point.location.y), transform=transform)

                if use_rotation_noise:
                    noise_rotation_degrees = random.uniform(-noise_limit_degrees, noise_limit_degrees)
                    use.rotate(angle = math.degrees(noise_rotation_degrees), center = (point.location.x, -point.location.y))

                self.svg.add(use)

            logger.info("end create uses for Circle packing")

class SVGPath():
    svg_matrix = mathutils.Matrix((
        [1.0, 0.0, 0.0, 0.0],
        [0.0, -1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, 1.0]))

    def __init__(self, spline, matrix_world, scale):
        self.spline = spline
        self.matrix_world = matrix_world
        self.scale = scale
        self.ds = []

        self.append_move_to()
        self.append_bezier_curve()
        self.append_end()

        self.d = ' '.join(self.ds)

    def append_move_to(self):
        m = self.get_global_pos(self.spline.bezier_points[0].co)
        self.ds.append("M{0},{1}".format(m.x, m.y))

    def append_bezier_curve(self):
        for i in range(len(self.spline.bezier_points) - 1):
            p1 = self.spline.bezier_points[i]
            p2 = self.spline.bezier_points[i + 1]

            c1 = self.get_global_pos(p1.handle_right)
            c2 = self.get_global_pos(p2.handle_left)
            c = self.get_global_pos(p2.co)

            self.ds.append("C {0},{1} {2},{3} {4},{5}".format(c1.x, c1.y, c2.x, c2.y, c.x, c.y))

    def append_end(self):
        start_point = self.spline.bezier_points[0]
        end_point = self.spline.bezier_points[-1]

        c1 = self.get_global_pos(end_point.handle_right)
        c2 = self.get_global_pos(start_point.handle_left)
        c = self.get_global_pos(start_point.co)

        self.ds.append("C {0},{1} {2},{3} {4},{5}".format(c1.x, c1.y, c2.x, c2.y, c.x, c.y))

    def get_global_pos(self, vec):
        v = vec.copy()
        v.resize_4d()

        w = self.svg_matrix @ v
        w = w * self.scale
        w.resize_3d()
        return w

class SVGUse():
    def __init__(self, id, location):
        self.id = id
        self.x = location[0]
        self.y = location[1]
        self.z = location[2]

    def get_location(self):
        return mathutils.Vector((self.x, self.y, self.z))

class SVGPoint():
    def __init__(self, location, collection=0, rotate=0.0, radius=0.0):
        self.location = location
        self.collection = collection
        self.rotate = rotate
        self.radius = radius

classes = (
    SvgExporter,
)

def register():
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)

def unregister():
    from bpy.utils import unregister_class
    for cls in classes:
        unregister_class(cls)





