import bpy
from bpy.types import Operator
from mathutils import Vector, Quaternion
import json
import math
import datetime


def get_camera_position(camera_object, three_js=False):
    """Get position of camera

    Args:
        camera_object: Blender camera object
        three_js: Exports for three-js if true, otherwise for Blender.

    Returns:
        The camera location as [X, Y, Z]
    """

    camera_location = camera_object.location

    if three_js:
        # Account for Y-UP axis orientation
        return [camera_location.x, camera_location.z, -camera_location.y]
    else:
        return [camera_location.x, camera_location.y, camera_location.z]


def get_camera_position_blender(camera_object):
    """Get position of camera in Blender format (Z-up)

    Args:
        camera_object: Blender camera object

    Returns:
        The camera location as [X, Y, Z] in Blender coordinates
    """
    camera_location = camera_object.location
    return [camera_location.x, camera_location.y, camera_location.z]


def get_camera_quaternion(camera_object, three_js=False):
    """Get quaternion of camera

    Args:
        camera_object: Blender camera object
        three_js: Exports for three-js if true, otherwise for Blender.

    Returns:
        Quaternion as [W, X, Y, Z] for Blender, or [X, Y, Z, W] for three-js
    """

    camera_matrix = camera_object.matrix_world.copy()

    if three_js:
        # Convert to Y-UP - same way normal blender gltf exporter does
        correction = Quaternion((2**0.5 / 2, -(2**0.5) / 2, 0.0, 0.0))
        camera_matrix @= correction.to_matrix().to_4x4()
        corrected_quaternion = camera_matrix.to_quaternion()

        # Account for Y-UP axis orientation
        return [
            corrected_quaternion.x,
            corrected_quaternion.z,
            -corrected_quaternion.y,
            corrected_quaternion.w,
        ]
    else:
        quaternion = camera_matrix.to_quaternion()
        return [quaternion.w, quaternion.x, quaternion.y, quaternion.z]


def get_camera_quaternion_blender(camera_object):
    """Get quaternion of camera in Blender format (Z-up, WXYZ)

    Args:
        camera_object: Blender camera object

    Returns:
        Quaternion as [W, X, Y, Z] in Blender coordinates
    """
    camera_matrix = camera_object.matrix_world.copy()
    quaternion = camera_matrix.to_quaternion()
    return [quaternion.w, quaternion.x, quaternion.y, quaternion.z]


def get_camera_lens(camera_object, three_js=False):
    """Get lens parameters of camera

    Args:
        camera_object: Blender camera object
        three_js: Exports for three-js if true, otherwise for Blender.

    Returns:
        Focal length for Blender, or field of view (fov) for three-js
    """

    camera_data = camera_object.data

    if three_js:
        render = bpy.context.scene.render
        width = render.pixel_aspect_x * render.resolution_x
        height = render.pixel_aspect_y * render.resolution_y
        aspect_ratio = width / height

        if width >= height:
            if camera_data.sensor_fit != "VERTICAL":
                camera_fov = 2.0 * math.atan(
                    math.tan(camera_data.angle * 0.5) / aspect_ratio
                )
            else:
                camera_fov = camera_data.angle
        else:
            if camera_data.sensor_fit != "HORIZONTAL":
                camera_fov = camera_data.angle
            else:
                camera_fov = 2.0 * math.atan(
                    math.tan(camera_data.angle * 0.5) / aspect_ratio
                )

        # Convert from radians to degrees
        return camera_fov * (180 / math.pi)
    else:
        return camera_data.lens


def get_camera_fov_blender(camera_object):
    """Get vertical field of view of camera in Blender format (degrees)
    Always returns vertical FOV by temporarily switching sensor fit if needed

    Args:
        camera_object: Blender camera object

    Returns:
        Vertical field of view in degrees (matching Blender's interface when set to VERTICAL)
    """
    camera_data = camera_object.data
    
    # Store original sensor fit
    original_sensor_fit = camera_data.sensor_fit
    
    # Temporarily switch to VERTICAL to get the exact vertical FOV that Blender calculates
    camera_data.sensor_fit = "VERTICAL"
    
    # Get the vertical FOV (camera.angle is now vertical FOV)
    vertical_fov_radians = camera_data.angle
    
    # Restore original sensor fit
    camera_data.sensor_fit = original_sensor_fit
    
    # Convert from radians to degrees
    return vertical_fov_radians * (180 / math.pi)


def get_camera_aspect_ratio(camera_object):
    """Get aspect ratio of the camera"""
    render = bpy.context.scene.render
    width = render.pixel_aspect_x * render.resolution_x
    height = render.pixel_aspect_y * render.resolution_y
    return width / height


def calculate_camera_intersection(camera_object, model, three_js):
    """Calculate 3D point on model surface where central camera ray intersects.
    I.e. the point on the 3D model that aligns with the centre of the matched
    image

    Args:
        camera_object: Blender camera object
        model: Blender 3D model
        three_js: Exports for three-js if true, otherwise for Blender.

    Returns:
        3D point as [X, Y, Z]
    """

    # vector along direction camera points
    camera_direction = Vector((0, 0, -1))
    camera_direction.rotate(camera_object.rotation_euler)
    camera_direction.normalize()

    # get the position/direction relative to the model
    matrix = model.matrix_world.copy()
    matrix_inv = matrix.inverted()
    ray_origin = camera_object.location
    ray_target = ray_origin + camera_direction
    
    ray_origin_obj = matrix_inv @ ray_origin
    ray_target_obj = matrix_inv @ ray_target
    ray_direction_obj = ray_target_obj - ray_origin_obj

    # Get hit position
    cast_result = model.ray_cast(ray_origin_obj, ray_direction_obj)
    hit_position = matrix @ cast_result[1]

    if three_js:
        # Account for Y-UP axis orientation
        return [hit_position.x, hit_position.z, -hit_position.y]
    else:
        return [hit_position.x, hit_position.y, hit_position.z]


def calculate_camera_intersection_blender(camera_object, model):
    """Calculate 3D point on model surface where central camera ray intersects in Blender format

    Args:
        camera_object: Blender camera object
        model: Blender 3D model

    Returns:
        3D point as [X, Y, Z] in Blender coordinates
    """

    # vector along direction camera points
    camera_direction = Vector((0, 0, -1))
    camera_direction.rotate(camera_object.rotation_euler)
    camera_direction.normalize()

    # get the position/direction relative to the model
    matrix = model.matrix_world.copy()
    matrix_inv = matrix.inverted()
    ray_origin = camera_object.location
    ray_target = ray_origin + camera_direction
    
    ray_origin_obj = matrix_inv @ ray_origin
    ray_target_obj = matrix_inv @ ray_target
    ray_direction_obj = ray_target_obj - ray_origin_obj

    # Get hit position
    cast_result = model.ray_cast(ray_origin_obj, ray_direction_obj)
    hit_position = matrix @ cast_result[1]

    return [hit_position.x, hit_position.y, hit_position.z]


def convert_camera_settings(camera_object, model, three_js=False):
    """Get summary of camera settings. All ThreeJS export options are
    based on the official blender GLTF exporter plugin.

    Args:
        camera_object: Blender camera object
        model: Blender 3D model
        three_js: Exports for three-js if true, otherwise for Blender.

    Returns:
        Dictionary with the following keys -
        camera_fov - camera field of view (only for three-js)
        camera_focal_length - camera focal length (only for Blender)
        camera_quaternion - camera quaternion
        camera_position - camera position
        camera_near - camera clip start
        camera_far - camera clip end
        center_model_point - point on 3D model surface where central camera ray intersects
    """

    camera_data = camera_object.data
    match = {}

    lens = get_camera_lens(camera_object, three_js)
    if three_js:
        match["camera_fov"] = lens
    else:
        match["camera_focal_length"] = lens

    match["camera_quaternion"] = get_camera_quaternion(camera_object, three_js)
    match["camera_position"] = get_camera_position(camera_object, three_js)

    match["camera_near"] = camera_data.clip_start
    match["camera_far"] = camera_data.clip_end

    match["centre_model_point"] = calculate_camera_intersection(
        camera_object, model, three_js
    )

    return match


def format_as_typescript_object(camera_object, model, settings):
    """Format camera parameters as TypeScript object string
    
    Args:
        camera_object: Blender camera object
        model: Blender 3D model
        settings: Image match settings from context
        
    Returns:
        Formatted TypeScript object string
    """
    
    # Get camera parameters in Blender format (Z-up, WXYZ quaternions)
    position = get_camera_position_blender(camera_object)
    quaternion = get_camera_quaternion_blender(camera_object)
    fov = get_camera_fov_blender(camera_object)  # Always vertical FOV
    aspect = get_camera_aspect_ratio(camera_object)
    
    # Get custom properties from camera
    ts_id = camera_object.get("ts_export_id", "camera-1")
    ts_name = camera_object.get("ts_export_name", "Camera View")
    ts_category = camera_object.get("ts_export_category", "default")
    ts_datetime = camera_object.get("ts_export_datetime", "2024-01-01T00:00:00Z")
    ts_description = camera_object.get("ts_export_description", "Camera view description")
    ts_tags = camera_object.get("ts_export_tags", "camera, view")
    
    # Get reference image path from current image match if available
    reference_image = "/path/to/image.jpg"
    if settings.current_image_name in settings.image_matches:
        current_image = settings.image_matches[settings.current_image_name]
        if current_image.movie_clip and current_image.movie_clip.filepath:
            reference_image = current_image.movie_clip.filepath
    
    # Format the TypeScript object
    ts_object = f'''  "{ts_id}": {{
    id: "{ts_id}",
    name: "{ts_name}",
    category: "{ts_category}",
    datetime: "{ts_datetime}",
    camera: {{
      position: [{position[0]:.6f}, {position[1]:.6f}, {position[2]:.6f}] as const,
      quaternion: [{quaternion[0]:.6f}, {quaternion[1]:.6f}, {quaternion[2]:.6f}, {quaternion[3]:.6f}] as const,
      fov: {fov:.4f},
      aspect: {aspect:.6f},
      sensorFit: "VERTICAL",
    }},
    referenceImage: "{reference_image}",
    description: "{ts_description}",
    tags: [{', '.join(f'"{tag.strip()}"' for tag in ts_tags.split(',') if tag.strip())}],
  }},'''
    
    return ts_object


def format_scene_camera_as_typescript_object(camera_object):
    """Format scene camera parameters as TypeScript object string
    
    Args:
        camera_object: Blender camera object (scene camera)
        
    Returns:
        Formatted TypeScript object string
    """
    
    # Get camera parameters in Blender format (Z-up, WXYZ quaternions)
    position = get_camera_position_blender(camera_object)
    quaternion = get_camera_quaternion_blender(camera_object)
    fov = get_camera_fov_blender(camera_object)  # Always vertical FOV
    aspect = get_camera_aspect_ratio(camera_object)
    
    # Get custom properties from camera
    ts_id = camera_object.get("ts_export_id", camera_object.name.lower().replace(" ", "-"))
    ts_name = camera_object.get("ts_export_name", camera_object.name)
    ts_category = camera_object.get("ts_export_category", "default")
    ts_datetime = camera_object.get("ts_export_datetime", "2024-01-01T00:00:00Z")
    ts_description = camera_object.get("ts_export_description", f"Camera view from {camera_object.name}")
    ts_tags = camera_object.get("ts_export_tags", "camera, view")
    ts_reference_image = camera_object.get("ts_export_reference_image", "/path/to/image.jpg")
    
    # Format the TypeScript object
    ts_object = f'''  "{ts_id}": {{
    id: "{ts_id}",
    name: "{ts_name}",
    category: "{ts_category}",
    datetime: "{ts_datetime}",
    camera: {{
      position: [{position[0]:.6f}, {position[1]:.6f}, {position[2]:.6f}] as const,
      quaternion: [{quaternion[0]:.6f}, {quaternion[1]:.6f}, {quaternion[2]:.6f}, {quaternion[3]:.6f}] as const,
      fov: {fov:.4f},
      aspect: {aspect:.6f},
      sensorFit: "VERTICAL",
    }},
    referenceImage: "{ts_reference_image}",
    description: "{ts_description}",
    tags: [{', '.join(f'"{tag.strip()}"' for tag in ts_tags.split(',') if tag.strip())}],
  }},'''
    
    return ts_object


def export_to_json(matches, export_filepath):
    """Export image matches to JSON file"""

    output = {}
    output["image_matches"] = matches

    # Serializing json
    json_object = json.dumps(output, indent=4)

    # Writing to sample.json
    json_filepath = bpy.path.abspath(export_filepath)
    if not json_filepath.endswith(".json"):
        json_filepath += ".json"

    with open(json_filepath, "w") as outfile:
        outfile.write(json_object)


class OBJECT_OT_export_matches(Operator):
    """Exports all image match settings to the specified JSON file with either
    Blender or ThreeJS settings"""

    bl_idname = "imagematches.export_matches"
    bl_label = "Export matches"

    def execute(self, context):
        settings = context.scene.match_settings

        if settings.model is None:
            self.report({"ERROR"}, "No 3D model selected")
            return {"CANCELLED"}

        if settings.export_filepath == "":
            self.report({"ERROR"}, "No export filepath selected")
            return {"CANCELLED"}

        if settings.export_type == "THREEJS":
            three_js = True
        else:
            three_js = False

        matches = []

        for image_match in settings.image_matches:
            camera = image_match.camera

            match = convert_camera_settings(camera, settings.model, three_js)
            match["image_filename"] = image_match.full_name
            matches.append(match)

        export_to_json(matches, settings.export_filepath)

        return {"FINISHED"}


class OBJECT_OT_copy_typescript_object(Operator):
    """Copy current camera parameters as TypeScript object to clipboard"""

    bl_idname = "imagematches.copy_typescript_object"
    bl_label = "Copy as TypeScript Object"

    def execute(self, context):
        settings = context.scene.match_settings

        if settings.model is None:
            self.report({"ERROR"}, "No 3D model selected")
            return {"CANCELLED"}

        if settings.current_image_name == "":
            self.report({"ERROR"}, "No image selected")
            return {"CANCELLED"}

        # Get current camera
        current_image = settings.image_matches[settings.current_image_name]
        camera = current_image.camera

        # Check if properties exist
        required_props = ["ts_export_id", "ts_export_name", "ts_export_category", 
                         "ts_export_datetime", "ts_export_description", "ts_export_tags"]
        if not all(prop in camera for prop in required_props):
            self.report({"ERROR"}, "Camera TypeScript properties not initialized. Use 'Initialize Properties' button first.")
            return {"CANCELLED"}

        # Format as TypeScript object
        ts_object = format_as_typescript_object(camera, settings.model, settings)

        # Copy to clipboard
        context.window_manager.clipboard = ts_object

        camera_id = camera.get("ts_export_id", "camera")
        self.report({"INFO"}, f"TypeScript object copied to clipboard for ID: {camera_id}")

        return {"FINISHED"}


class OBJECT_OT_copy_all_typescript_objects(Operator):
    """Copy all camera parameters as TypeScript objects to clipboard"""

    bl_idname = "imagematches.copy_all_typescript_objects"
    bl_label = "Copy All as TypeScript Objects"

    def execute(self, context):
        settings = context.scene.match_settings

        if settings.model is None:
            self.report({"ERROR"}, "No 3D model selected")
            return {"CANCELLED"}

        if len(settings.image_matches) == 0:
            self.report({"ERROR"}, "No images loaded")
            return {"CANCELLED"}

        ts_objects = []
        required_props = ["ts_export_id", "ts_export_name", "ts_export_category", 
                         "ts_export_datetime", "ts_export_description", "ts_export_tags"]
        
        for i, image_match in enumerate(settings.image_matches):
            camera = image_match.camera
            
            # Check if properties exist, skip if not
            if not all(prop in camera for prop in required_props):
                self.report({"WARNING"}, f"Skipping {camera.name} - properties not initialized")
                continue
                
            ts_object = format_as_typescript_object(camera, settings.model, settings)
            ts_objects.append(ts_object)

        if not ts_objects:
            self.report({"ERROR"}, "No cameras with initialized TypeScript properties found")
            return {"CANCELLED"}

        # Join all objects
        full_output = "\n".join(ts_objects)

        # Copy to clipboard
        context.window_manager.clipboard = full_output

        self.report({"INFO"}, f"Copied {len(ts_objects)} TypeScript objects to clipboard")

        return {"FINISHED"}


class OBJECT_OT_copy_scene_camera_typescript(Operator):
    """Copy scene camera parameters as TypeScript object to clipboard"""

    bl_idname = "view3d.copy_scene_camera_typescript"
    bl_label = "Copy Scene Camera as TypeScript Object"

    def execute(self, context):
        if not context.scene.camera:
            self.report({"ERROR"}, "No active camera in scene")
            return {"CANCELLED"}

        camera = context.scene.camera

        # Check if properties exist
        required_props = ["ts_export_id", "ts_export_name", "ts_export_category", 
                         "ts_export_datetime", "ts_export_reference_image",
                         "ts_export_description", "ts_export_tags"]
        if not all(prop in camera for prop in required_props):
            self.report({"ERROR"}, "Camera TypeScript properties not initialized. Use 'Initialize Properties' button first.")
            return {"CANCELLED"}

        # Format as TypeScript object
        ts_object = format_scene_camera_as_typescript_object(camera)

        # Copy to clipboard
        context.window_manager.clipboard = ts_object

        camera_id = camera.get("ts_export_id", camera.name)
        self.report({"INFO"}, f"Scene camera TypeScript object copied to clipboard for ID: {camera_id}")

        return {"FINISHED"}


class OBJECT_OT_init_camera_typescript_properties(Operator):
    """Initialize TypeScript export properties on camera object"""

    bl_idname = "camera.init_typescript_properties"
    bl_label = "Initialize TypeScript Properties"

    camera_name: bpy.props.StringProperty(name="Camera Name")

    def execute(self, context):
        if self.camera_name:
            camera = bpy.data.objects.get(self.camera_name)
        elif context.active_object and context.active_object.type == 'CAMERA':
            camera = context.active_object
        elif context.scene.camera:
            camera = context.scene.camera
        else:
            self.report({"ERROR"}, "No camera found")
            return {"CANCELLED"}

        if camera.type != 'CAMERA':
            self.report({"ERROR"}, "Selected object is not a camera")
            return {"CANCELLED"}

        # Initialize properties
        if "ts_export_id" not in camera:
            camera["ts_export_id"] = camera.name.lower().replace(" ", "-").replace("_", "-")
        if "ts_export_name" not in camera:
            camera["ts_export_name"] = camera.name
        if "ts_export_category" not in camera:
            camera["ts_export_category"] = "default"
        if "ts_export_datetime" not in camera:
            camera["ts_export_datetime"] = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        if "ts_export_reference_image" not in camera:
            camera["ts_export_reference_image"] = "/path/to/image.jpg"
        if "ts_export_description" not in camera:
            camera["ts_export_description"] = f"Camera view from {camera.name}"
        if "ts_export_tags" not in camera:
            camera["ts_export_tags"] = "camera, view"

        self.report({"INFO"}, f"Initialized TypeScript properties for {camera.name}")
        return {"FINISHED"}


class OBJECT_OT_copy_selected_camera_typescript(Operator):
    """Copy selected camera parameters as TypeScript object to clipboard"""

    bl_idname = "view3d.copy_selected_camera_typescript"
    bl_label = "Copy Selected Camera as TypeScript Object"

    def execute(self, context):
        if not context.active_object or context.active_object.type != 'CAMERA':
            self.report({"ERROR"}, "No camera selected")
            return {"CANCELLED"}

        camera = context.active_object

        # Check if properties exist
        required_props = ["ts_export_id", "ts_export_name", "ts_export_category", 
                         "ts_export_datetime", "ts_export_reference_image",
                         "ts_export_description", "ts_export_tags"]
        if not all(prop in camera for prop in required_props):
            self.report({"ERROR"}, "Camera TypeScript properties not initialized. Use 'Initialize Properties' button first.")
            return {"CANCELLED"}

        # Format as TypeScript object
        ts_object = format_scene_camera_as_typescript_object(camera)

        # Copy to clipboard
        context.window_manager.clipboard = ts_object

        camera_id = camera.get("ts_export_id", camera.name)
        self.report({"INFO"}, f"Selected camera TypeScript object copied to clipboard for ID: {camera_id}")

        return {"FINISHED"}