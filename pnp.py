""" Adapted from original code from Roger Torm, RT Studios Camera Pnpoint plugin
https://rtstudios.gumroad.com/l/camera_pnpoint """

import bpy
import cv2 as cv
import numpy as np
from mathutils import Matrix, Vector
import time


def get_optical_centre(clip_camera):
    """Get optical centre of given camera"""

    if bpy.app.version < (3, 5, 0):
        optical_centre = clip_camera.principal
    else:
        optical_centre = clip_camera.principal_point_pixels

    return optical_centre


def set_optical_centre(clip_camera, optical_centre):
    """Set optical centre of given camera"""

    if bpy.app.version < (3, 5, 0):
        clip_camera.principal = optical_centre
    else:
        clip_camera.principal_point_pixels = optical_centre

def get_2D_3D_point_coordinates(self, point_matches, clip, frame):
    """Get coordinates of all 2D-3D point matches. Discards any matches with
    only a 2D point or only a 3D point.

    Args:
        point_matches: current point matches
        clip: current Blender movie clip
        frame: The current frame number for retrieving marker coordinates

    Returns:
        Two numpy arrays of equal size - the first being the coordinates of all
        2D points, and the second the coordinates of all 3D points
    """
    size = clip.size
    tracks = clip.tracking.objects[0].tracks

    if not tracks:
        self.report({"ERROR"}, "Please add markers for the 2D points")
        return np.array([]), np.array([])

    points_2d_coords = []
    points_3d_coords = []
    points_ignored = False

    for point_match in point_matches:
        # Only process matches with both 2D and 3D points initialized -
        # rest ignored
        if point_match.is_point_2d_initialised and point_match.is_point_3d_initialised:
            points_3d_coords.append(point_match.point_3d.location)

            track = tracks[point_match.point_2d]
            marker = track.markers.find_frame(frame, exact=True)
            if marker and not marker.mute:
                # .co runs from 0 to 1 on each axis of the image, so multiply
                # by image size to get full coordinates
                point_2d_coordinates = [
                    marker.co[0] * size[0],
                    size[1] - marker.co[1] * size[1]
                ]
                points_2d_coords.append(point_2d_coordinates)
            else:
                points_ignored = True
        else:
            points_ignored = True

    if points_ignored and hasattr(self, 'report'):
        self.report({"WARNING"}, "Ignoring points with only 2D or only 3D")

    points_2d_coords = np.asarray(points_2d_coords, dtype="double")
    points_3d_coords = np.asarray(points_3d_coords, dtype="double")

    return points_2d_coords, points_3d_coords


def get_distortion_coefficients(self, clip_camera):
    """Get distortion coefficients of given camera as a numpy array of
    np.array([k1, k2, 0, 0, k3])"""

    # take radial distortion parameters:
    if clip_camera.distortion_model == "POLYNOMIAL":
        k1, k2, k3 = clip_camera.k1, clip_camera.k2, clip_camera.k3
    elif clip_camera.distortion_model == "BROWN":
        k1, k2, k3 = (
            clip_camera.brown_k1,
            clip_camera.brown_k2,
            clip_camera.brown_k3,
        )
    else:
        # Unsupported distortion model - just set to defaults of 0
        k1, k2, k3 = 0.0, 0.0, 0.0
        if hasattr(self, 'report'):
            self.report(
                {"WARNING"},
                "Current distortion model is not supported, use Polynomial instead.",
            )

    # construct distortion vector, only k1,k2,k3 (polynomial or brown models)
    distortion_coefficients = np.array([k1, k2, 0, 0, k3])

    return distortion_coefficients


def get_camera_intrinsics(clip_camera, clip_size):
    """Get array of intrinsics for given camera + movie clip size

    Args:
        clip_camera: Blender movie clip camera
        clip_size: Blender movie clip size

    Returns:
        Numpy array of camera intrinsics
    """
    focal = clip_camera.focal_length_pixels
    optical_centre = get_optical_centre(clip_camera)

    # construct camera intrinsics
    camera_intrinsics = np.array(
        [
            [focal, 0, optical_centre[0]],
            [0, focal, clip_size[1] - optical_centre[1]],
            [0, 0, 1],
        ],
        dtype="double",
    )

    return camera_intrinsics


def get_scene_info(self, context):
    """Collect information from the movie clip and its camera, as well as
    2D and 3D points from the current image match

    Args:
        context: Blender context

    Returns:
        self - self from Blender operator
        context - Blender context
        clip - current Blender movie clip
        points_3d_coords - numpy array of 3D point coordinates
        points_2d_coords - numpy array of 2D point coordinates
        camera_intrinsics - numpy array of camera intrinsics
        distortion_coefficients - numpy array of camera distortion coefficients
    """

    settings = context.scene.match_settings
    current_image = settings.image_matches[settings.current_image_name]
    frame = bpy.data.scenes[0].frame_current

    clip = current_image.movie_clip

    # get picture and camera metrics
    size = clip.size
    clip_camera = clip.tracking.camera

    points_2d_coords, points_3d_coords = get_2D_3D_point_coordinates(
        self, current_image.point_matches, clip, frame
    )
    camera_intrinsics = get_camera_intrinsics(clip_camera, size)
    distortion_coefficients = get_distortion_coefficients(self, clip_camera)


    return (
        self,
        context,
        clip,
        points_3d_coords,
        points_2d_coords,
        camera_intrinsics,
        distortion_coefficients,
        frame,
    )

def solve_pnp(
    self,
    context,
    clip,
    points_3d_coords,
    points_2d_coords,
    camera_intrinsics,
    distortion_coefficients,
    frame
):
    """Solve camera pose with OpenCV's PNP solver. Set the current camera
    intrinsics, extrinsics and background image to match

    Args:
        context: Blender context
        clip: Blender movie clip
        points_3d_coords: numpy array of 3D point coordinates
        points_2d_coords: numpy array of 2D point coordinates
        camera_intrinsics: numpy array of camera intrinsics
        distortion_coefficients: numpy array of camera distortion coefficients
        frame: The current frame number for keyframe insertion

    Returns:
        Status for operator - cancelled or finished
    """

    npoints = points_3d_coords.shape[0]
    size = clip.size

    if npoints < 4:
        if hasattr(self, 'report'):
            self.report(
                {"ERROR"},
                "Not enough point pairs, use at least 4 markers to solve a camera pose.",
            )
        return {"CANCELLED"}

    # solve Perspective-n-Point
    ret, rvec, tvec, error = cv.solvePnPGeneric(
        points_3d_coords,
        points_2d_coords,
        camera_intrinsics,
        distortion_coefficients,
        flags=cv.SOLVEPNP_SQPNP,
    )  # TODO: further investigation on other algorithms
    rmat, _ = cv.Rodrigues(rvec[0])

    settings = context.scene.match_settings
    settings.pnp_solve_msg = (
        ("Reprojection Error: %.2f" % error) if ret else "solvePnP failed!"
    )

    # calculate projection errors for each point pair
    print("dbg: calculating projections of 3d points...")
    impoints, jacob = cv.projectPoints(
        points_3d_coords,
        rvec[0],
        tvec[0],
        camera_intrinsics,
        distortion_coefficients,
    )
    print("dbg: projection finished")
    print(impoints)
    print(jacob)

    # get R and T matrices
    # https://blender.stackexchange.com/questions/38009/3x4-camera-matrix-from-blender-camera
    R_world2cv = Matrix(rmat.tolist())
    T_world2cv = Vector(tvec[0])

    # blender camera to opencv camera coordinate conversion
    R_bcam2cv = Matrix(((1, 0, 0), (0, -1, 0), (0, 0, -1)))

    # calculate transform in world coordinates
    R_cv2world = R_world2cv.transposed()
    rot = R_cv2world @ R_bcam2cv
    loc = -1 * R_cv2world @ T_world2cv

    # Set camera intrinsics, extrinsics and background
    current_image = settings.image_matches[settings.current_image_name]
    camera = current_image.camera
    tracking_camera = clip.tracking.camera

    camera_data = camera.data
    camera_data.type = "PERSP"
    camera_data.lens = tracking_camera.focal_length
    camera_data.sensor_width = tracking_camera.sensor_width
    camera_data.sensor_height = (
        tracking_camera.sensor_width * size[1] / size[0]
    )
    render_size = [
        context.scene.render.pixel_aspect_x
        * context.scene.render.resolution_x,
        context.scene.render.pixel_aspect_y
        * context.scene.render.resolution_y,
    ]
    camera_data.sensor_fit = (
        "HORIZONTAL"
        if render_size[0] / render_size[1] <= size[0] / size[1]
        else "VERTICAL"
    )
    refsize = (
        size[0]
        if render_size[0] / render_size[1] <= size[0] / size[1]
        else size[1]
    )

    optical_centre = get_optical_centre(tracking_camera)
    camera_data.shift_x = (size[0] * 0.5 - optical_centre[0]) / refsize
    camera_data.shift_y = (size[1] * 0.5 - optical_centre[1]) / refsize

    camera_data.show_background_images = True
    if not camera_data.background_images:
        background_image = camera_data.background_images.new()
    else:
        background_image = camera_data.background_images[0]
    background_image.source = "MOVIE_CLIP"
    background_image.clip = clip
    background_image.frame_method = "FIT"
    background_image.display_depth = "FRONT"
    background_image.clip_user.use_render_undistorted = True

    camera.matrix_world = Matrix.Translation(loc) @ rot.to_4x4()
    
    # Insert keyframes for animation only if auto keyframe is enabled or not in live mode
    if not hasattr(settings, 'live_solve_enabled') or not settings.live_solve_enabled or settings.live_solve_auto_keyframe:
        camera.keyframe_insert(data_path="location", frame=frame)
        camera.keyframe_insert(data_path="rotation_euler", frame=frame)
        camera.data.keyframe_insert(data_path="shift_x", frame=frame)
        camera.data.keyframe_insert(data_path="shift_y", frame=frame)
        camera.data.keyframe_insert(data_path="lens", frame=frame)
        camera.data.keyframe_insert(data_path="sensor_height", frame=frame)
        camera.data.keyframe_insert(data_path="sensor_fit", frame=frame)

    context.scene.camera = camera

    return {"FINISHED"}


def calibrate_camera(
    self,
    context,
    clip,
    points_3d_coords,
    points_2d_coords,
    camera_intrinsics,
    distortion_coefficients,
    frame,
):
    """Calibrate current tracking camera using openCV. Sets the intrinsics
    that are currently specified in the settings.

    Args:
        context: Blender context
        clip: Blender movie clip
        points_3d_coords: numpy array of 3D point coordinates
        points_2d_coords: numpy array of 2D point coordinates
        camera_intrinsics: numpy array of camera intrinsics
        distortion_coefficients: numpy array of camera distortion coefficients

    Returns:
        Status for operator - cancelled or finished
    """

    settings = context.scene.match_settings
    npoints = points_3d_coords.shape[0]
    size = clip.size

    if npoints < 6:
        self.report(
            {"ERROR"},
            "Not enough point pairs, use at least 6 markers to calibrate a camera.",
        )
        return {"CANCELLED"}

    flags = (
        cv.CALIB_USE_INTRINSIC_GUESS
        + cv.CALIB_FIX_ASPECT_RATIO
        + cv.CALIB_ZERO_TANGENT_DIST
        + (
            cv.CALIB_FIX_PRINCIPAL_POINT
            if not settings.calibrate_principal_point
            else 0
        )
        + (
            cv.CALIB_FIX_FOCAL_LENGTH
            if not settings.calibrate_focal_length
            else 0
        )
        + (cv.CALIB_FIX_K1 if not settings.calibrate_distortion_k1 else 0)
        + (cv.CALIB_FIX_K2 if not settings.calibrate_distortion_k2 else 0)
        + (cv.CALIB_FIX_K3 if not settings.calibrate_distortion_k3 else 0)
    )

    ret, camera_intrinsics, distortion_coefficients, _, _ = cv.calibrateCamera(
        np.asarray([points_3d_coords], dtype="float32"),
        np.asarray([points_2d_coords], dtype="float32"),
        size,
        camera_intrinsics,
        distortion_coefficients,
        flags=flags,
    )

    settings.pnp_calibrate_msg = "Reprojection Error: %.2f" % ret

    # set picture and camera metrics
    tracking_camera = clip.tracking.camera

    if settings.calibrate_focal_length:
        tracking_camera.focal_length_pixels = camera_intrinsics[0][0]

    if settings.calibrate_principal_point:
        optical_centre = [
            camera_intrinsics[0][2],
            size[1] - camera_intrinsics[1][2],
        ]
        set_optical_centre(tracking_camera, optical_centre)

    if (
        settings.calibrate_distortion_k1
        or settings.calibrate_distortion_k2
        or settings.calibrate_distortion_k3
    ):
        tracking_camera.k1 = distortion_coefficients[0]
        tracking_camera.k2 = distortion_coefficients[1]
        tracking_camera.k3 = distortion_coefficients[4]
        tracking_camera.brown_k1 = distortion_coefficients[0]
        tracking_camera.brown_k2 = distortion_coefficients[1]
        tracking_camera.brown_k3 = distortion_coefficients[4]

    return {"FINISHED"}


def solve_sequence_pnp(self, context):
    """Solve camera pose for each frame in the current frame range."""
    scene = context.scene
    start_frame = scene.frame_start
    end_frame = scene.frame_end
    for frame in range(start_frame, end_frame + 1):
        scene.frame_set(frame)
        solve_pnp(*get_scene_info(self, context))
    return {"FINISHED"}


def get_current_state_hash(context):
    """Get a hash of current point positions and camera parameters for change detection"""
    try:
        settings = context.scene.match_settings
        if settings.current_image_name not in settings.image_matches:
            return None
            
        current_image = settings.image_matches[settings.current_image_name]
        clip = current_image.movie_clip
        
        if not clip:
            return None
            
        state_data = []
        
        # Get 2D point positions
        tracks = clip.tracking.objects[0].tracks
        frame = bpy.data.scenes[0].frame_current
        
        for point_match in current_image.point_matches:
            if point_match.is_point_2d_initialised and point_match.is_point_3d_initialised:
                # 2D point position
                track = tracks[point_match.point_2d]
                marker = track.markers.find_frame(frame, exact=True)
                if marker and not marker.mute:
                    state_data.extend([marker.co[0], marker.co[1]])
                
                # 3D point position
                point_3d = point_match.point_3d
                state_data.extend([point_3d.location[0], point_3d.location[1], point_3d.location[2]])
        
        # Get camera parameters
        tracking_camera = clip.tracking.camera
        state_data.extend([
            tracking_camera.focal_length_pixels,
            tracking_camera.k1,
            tracking_camera.k2,
            tracking_camera.k3,
        ])
        
        optical_centre = get_optical_centre(tracking_camera)
        state_data.extend([optical_centre[0], optical_centre[1]])
        
        # Convert to string for hashing
        state_str = "_".join([f"{x:.6f}" for x in state_data])
        return hash(state_str)
        
    except Exception as e:
        print(f"Error getting state hash: {e}")
        return None


class PNP_OT_reset_camera(bpy.types.Operator):
    """Reset camera intrinsics to default values"""

    bl_idname = "pnp.reset_camera"
    bl_label = "Rest camera intrinsics"
    bl_options = {"UNDO"}

    def execute(self, context):
        settings = context.scene.match_settings
        current_image = settings.image_matches[settings.current_image_name]
        clip = current_image.movie_clip

        tracking_camera = clip.tracking.camera
        tracking_camera.focal_length = 24.0
        tracking_camera.principal_point = [0.0, 0.0]

        tracking_camera.k1 = 0.0
        tracking_camera.k2 = 0.0
        tracking_camera.k3 = 0.0
        tracking_camera.brown_k1 = 0.0
        tracking_camera.brown_k2 = 0.0
        tracking_camera.brown_k3 = 0.0

        return {"FINISHED"}


class PNP_OT_pose_camera(bpy.types.Operator):
    """Solve camera extrinsics using available 2D-3D point matches"""

    bl_idname = "pnp.solve_pnp"
    bl_label = "Solve camera extrinsics"
    bl_options = {"UNDO"}

    def execute(self, context):
        settings = context.scene.match_settings

        if settings.model.mode != "OBJECT":
            self.report({"ERROR"}, "Please switch to Object Mode")
            return {"CANCELLED"}

        # call solver
        return solve_pnp(*get_scene_info(self, context))


class PNP_OT_calibrate_camera(bpy.types.Operator):
    """Solve camera intrinsics using available 2D-3D point matches"""

    bl_idname = "pnp.calibrate_camera"
    bl_label = "Solve camera intrinsics"
    bl_options = {"UNDO"}

    def execute(self, context):
        settings = context.scene.match_settings

        if settings.model.mode != "OBJECT":
            self.report({"ERROR"}, "Please switch to Object Mode")
            return {"CANCELLED"}

        # call solver
        return calibrate_camera(*get_scene_info(self, context))


class PNP_OT_solve_sequence(bpy.types.Operator):
    """Solve camera extrinsics for each frame in the current frame range"""

    bl_idname = "pnp.solve_sequence_pnp"
    bl_label = "Solve camera extrinsics for sequence"
    bl_options = {"UNDO"}

    def execute(self, context):
        settings = context.scene.match_settings

        if settings.model.mode != "OBJECT":
            self.report({"ERROR"}, "Please switch to Object Mode")
            return {"CANCELLED"}

        return solve_sequence_pnp(self, context)


def update_current_frames(self, context):
    """Update camera pose for frames that have keyframes set."""
    scene = context.scene
    camera = context.scene.camera

    keyframes = set()
    if camera.animation_data and camera.animation_data.action:
        for fcurve in camera.animation_data.action.fcurves:
            for keyframe in fcurve.keyframe_points:
                keyframes.add(int(keyframe.co[0]))

    for frame in keyframes:
        scene.frame_set(frame)
        solve_pnp(*get_scene_info(self, context))

    return {"FINISHED"}


class PNP_OT_update_current_frames(bpy.types.Operator):
    """Update camera extrinsics for frames with existing keyframes"""

    bl_idname = "pnp.update_current_frames"
    bl_label = "Update camera extrinsics for existing keyframes"
    bl_options = {"UNDO"}

    def execute(self, context):
        settings = context.scene.match_settings

        if settings.model.mode != "OBJECT":
            self.report({"ERROR"}, "Please switch to Object Mode")
            return {"CANCELLED"}

        return update_current_frames(self, context)


class PNP_OT_live_solve_toggle(bpy.types.Operator):
    """Toggle live camera pose solving"""

    bl_idname = "pnp.live_solve_toggle"
    bl_label = "Toggle Live Solve"
    bl_options = {"REGISTER"}

    _timer = None
    _last_state_hash = None
    _frame_counter = 0
    _solving = False

    @classmethod
    def poll(cls, context):
        settings = context.scene.match_settings
        return (settings.current_image_name != "" and 
                settings.model is not None and
                settings.model.mode == "OBJECT")

    def modal(self, context, event):
        settings = context.scene.match_settings
        
        if not settings.live_solve_enabled:
            self.cancel(context)
            return {'CANCELLED'}

        if event.type == 'ESC':
            settings.live_solve_enabled = False
            self.cancel(context)
            return {'CANCELLED'}

        if event.type == 'TIMER':
            # Only check for changes every N frames based on update rate
            self._frame_counter += 1
            if self._frame_counter < settings.live_solve_update_rate:
                return {'PASS_THROUGH'}
            
            self._frame_counter = 0
            
            # Don't check if we're currently solving to avoid recursion
            if self._solving:
                return {'PASS_THROUGH'}
            
            # Get current state hash
            current_hash = get_current_state_hash(context)
            
            if current_hash is None:
                settings.live_solve_status = "Error: No valid data"
                return {'PASS_THROUGH'}
            
            # Check if state has changed
            if self._last_state_hash is not None and current_hash != self._last_state_hash:
                settings.live_solve_status = "Solving..."
                
                # Solve camera pose
                self._solving = True
                try:
                    scene_info = get_scene_info(self, context)
                    if scene_info:
                        result = solve_pnp(*scene_info)
                        if result == {"FINISHED"}:
                            settings.live_solve_status = f"Live solving - {settings.pnp_solve_msg}"
                        else:
                            settings.live_solve_status = "Solve failed"
                except Exception as e:
                    settings.live_solve_status = f"Error: {str(e)}"
                    print(f"Live solve error: {e}")
                finally:
                    self._solving = False
            elif self._last_state_hash is None:
                settings.live_solve_status = "Live solving active"
            
            self._last_state_hash = current_hash

        return {'PASS_THROUGH'}

    def execute(self, context):
        settings = context.scene.match_settings
        
        if settings.live_solve_enabled:
            # Stop live solving
            settings.live_solve_enabled = False
            settings.live_solve_status = "Stopped"
            return {'FINISHED'}
        else:
            # Start live solving
            settings.live_solve_enabled = True
            settings.live_solve_status = "Starting..."
            
            # Reset state
            self._last_state_hash = None
            self._frame_counter = 0
            self._solving = False
            
            # Add timer for modal operator
            wm = context.window_manager
            self._timer = wm.event_timer_add(0.1, window=context.window)
            wm.modal_handler_add(self)
            
            return {'RUNNING_MODAL'}

    def cancel(self, context):
        settings = context.scene.match_settings
        settings.live_solve_enabled = False
        settings.live_solve_status = "Stopped"
        
        wm = context.window_manager
        if self._timer:
            wm.event_timer_remove(self._timer)
            self._timer = None