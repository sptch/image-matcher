import bpy


def current_image_initialised(context):
    """Check if current image has been initialised"""
    settings = context.scene.match_settings
    return settings.current_image_name != ""


class POINT_UL_UI(bpy.types.UIList):
    """UI for 2D-3D point list"""

    def draw_item(
        self,
        context,
        layout,
        data,
        point,
        icon,
        active_data,
        active_propname,
        index,
    ):
        icon = "EMPTY_DATA"

        row = layout.row()

        col = layout.column()
        col.label(text=f"{index + 1}", icon=icon)

        col = layout.column()
        col.enabled = False
        col.prop(point, "is_point_2d_initialised", text="2D")

        col = layout.column()
        col.enabled = False
        col.prop(point, "is_point_3d_initialised", text="3D")

        col = layout.column()
        if point.is_point_2d_initialised:
            col.enabled = True
        else:
            col.enabled = False


class IMAGE_UL_UI(bpy.types.UIList):
    """UI for image list"""

    def draw_item(
        self,
        context,
        layout,
        data,
        image,
        icon,
        active_data,
        active_propname,
        index,
    ):
        settings = context.scene.match_settings

        icon = "IMAGE_PLANE"
        row = layout.row()

        col = layout.column()

        is_image_active = image.name == settings.current_image_name
        swap_operator = col.operator(
            "imagematches.swap_image",
            text="",
            icon=icon,
            depress=is_image_active,
        )
        swap_operator.image_name = image.name

        col = layout.column()
        col.label(text=image.name)
        
        #Delete image button
        col = layout.column(align=True)
        col.emboss = 'NONE'
        remove_op = col.operator("imagematches.remove_image", text="", icon="X")
        remove_op.index = index


class ImagePanel(bpy.types.Panel):
    """Panel to add or change current image"""

    bl_label = "Add / Change Image"
    bl_idname = "CLIP_PT_AddImage"
    bl_space_type = "CLIP_EDITOR"
    bl_region_type = "TOOLS"
    bl_category = "Image Match"
    

    def draw(self, context):
        layout = self.layout
        settings = context.scene.match_settings

        row = layout.row(align=True)
        row.label(text="Image filepath:")
        row.prop(settings, "image_filepath", text="")

        row = layout.row()
        row.operator("imagematches.add_image")

        row = layout.row()
        row.label(text="Loaded images:")

        row = layout.row()
        row.template_list(
            "IMAGE_UL_UI",
            "Image_List",
            settings,
            "image_matches",
            settings,
            "active_image_index",
            rows=3,
        )
        row = layout.row()
        row.operator(
            "imagematches.toggle_camera",
            text="Toggle camera view",
            icon="VIEW_CAMERA",
        )

        current_image = settings.image_matches[settings.current_image_name]
        if current_image is not None:
            row = layout.row(align=True)
            row.prop(
            current_image.camera.data,
            "clip_start",
            text="Clip start",
            )
            row.prop(
            current_image.camera.data,
            "clip_end",
            text="Clip end",
            )
            row = layout.row()
            row.prop(
            current_image.camera.data,
            "show_background_images",
            text="Show matched image",
            )
            row = layout.row()
            row.prop(
            current_image.camera.data.background_images[0],
            "alpha",
            text="Image opacity",
            )
           

       


class PointsPanel(bpy.types.Panel):
    """Panel for all 2D/3D point settings"""

    bl_label = "Points"
    bl_idname = "CLIP_PT_Points"
    bl_space_type = "CLIP_EDITOR"
    bl_region_type = "TOOLS"
    bl_category = "Image Match"

    @classmethod
    def poll(self, context):
        return current_image_initialised(context)

    def draw(self, context):
        layout = self.layout
        settings = context.scene.match_settings

        row = layout.row(align=True)
        row.label(text="3D model :")
        row.prop(settings, "model", text="")

        row = layout.row(align=True).split(factor=0.7, align=True)
        row.prop(settings, "point_3d_display_size", text="3D point size")
        row.operator("imagematches.update_3d_point_size", text="Update")
        # Bit of space between the display size and point mode
        row = layout.row()

        row = layout.row()
        row.label(text="Click to add, Ctrl + click to delete")

        if not settings.point_mode_enabled:
            mode_icon = "PLAY"
            mode_txt = "Point mode"
        else:
            mode_icon = "PAUSE"
            mode_txt = "Right click or ESC to cancel"

        row = layout.row(align=True)
        row.operator(
            "imagematches.point_mode",
            text=mode_txt,
            icon=mode_icon,
            depress=settings.point_mode_enabled,
        )

        row = layout.row()
        current_image = settings.image_matches[settings.current_image_name]
        row.template_list(
            "POINT_UL_UI",
            "Point_List",
            current_image,
            "point_matches",
            current_image,
            "active_point_index",
        )


class CurrentCameraSettings(bpy.types.Panel):
    """Collapsable sub-panel for current tracking camera settings"""

    bl_label = "Current camera settings"
    bl_idname = "CLIP_PT_PNP_Current_Settings"
    bl_space_type = "CLIP_EDITOR"
    bl_region_type = "TOOLS"
    bl_category = "Image Match"

    bl_parent_id = "CLIP_PT_PNP_Calibrate"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout

        settings = context.scene.match_settings
        current_image = settings.image_matches[settings.current_image_name]
        camera = current_image.movie_clip.tracking.camera

        col = layout.column()

        # Same as layout in right panel of clip editor under Track >
        # Camera > Lens
        if camera.units == "MILLIMETERS":
            col.prop(camera, "focal_length")
        else:
            col.prop(camera, "focal_length_pixels")
        col.prop(camera, "units", text="Units")

        col = layout.column()
        col.prop(camera, "principal_point", text="Optical Center")

        col = layout.column()
        col.prop(camera, "distortion_model", text="Lens Distortion")
        if camera.distortion_model == "POLYNOMIAL":
            col = layout.column(align=True)
            col.prop(camera, "k1")
            col.prop(camera, "k2")
            col.prop(camera, "k3")
        elif camera.distortion_model == "DIVISION":
            col = layout.column(align=True)
            col.prop(camera, "division_k1")
            col.prop(camera, "division_k2")
        elif camera.distortion_model == "NUKE":
            col = layout.column(align=True)
            col.prop(camera, "nuke_k1")
            col.prop(camera, "nuke_k2")
        elif camera.distortion_model == "BROWN":
            col = layout.column(align=True)
            col.prop(camera, "brown_k1")
            col.prop(camera, "brown_k2")
            col.prop(camera, "brown_k3")
            col.prop(camera, "brown_k4")
            col.separator()
            col.prop(camera, "brown_p1")
            col.prop(camera, "brown_p2")


class CalibratePanel(bpy.types.Panel):
    """Panel for all camera calibration settings"""

    bl_label = "PNP - calibrate camera"
    bl_idname = "CLIP_PT_PNP_Calibrate"
    bl_space_type = "CLIP_EDITOR"
    bl_region_type = "TOOLS"
    bl_category = "Image Match"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(self, context):
        return current_image_initialised(context)

    def draw(self, context):
        layout = self.layout
        settings = context.scene.match_settings

        col = layout.column(heading="Calibrate", align=True)
        col.prop(settings, "calibrate_focal_length", text="Focal Length")
        col.prop(settings, "calibrate_principal_point", text="Optical Center")
        row = col.row(align=True).split(factor=0.22)
        row.prop(settings, "calibrate_distortion_k1", text="K1")
        row = row.row(align=True).split(factor=0.3)
        row.prop(settings, "calibrate_distortion_k2", text="K2")
        row.prop(settings, "calibrate_distortion_k3", text="K3 Distortion")

        col = layout.column(align=True)
        col.operator("pnp.calibrate_camera", text="Calibrate Camera")

        row = layout.row()
        row.label(text=settings.pnp_calibrate_msg)

        row = layout.row(align=True)
        row.operator("pnp.reset_camera", text="Reset Camera")

class SolvePanel(bpy.types.Panel):
    """Panel for all PNP solver settings"""

    bl_label = "PNP - Solve Pose"
    bl_idname = "CLIP_PT_PNP_Solve"
    bl_space_type = "CLIP_EDITOR"
    bl_region_type = "TOOLS"
    bl_category = "Image Match"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(self, context):
        return current_image_initialised(context)

    def draw(self, context):
        layout = self.layout
        settings = context.scene.match_settings
        current_image = settings.image_matches[settings.current_image_name]

        # Manual solve buttons
        col = layout.column()
        col.label(text="Manual Solving:", icon="PLAY")
        
        row = col.row()
        row.operator("pnp.solve_pnp", text="Solve Camera Pose")
        row.scale_y = 1.5

        row = col.row()
        row.operator("pnp.solve_sequence_pnp", text="Solve Camera Pose for Sequence")
        row.scale_y = 1.2

        row = col.row()
        row.operator("pnp.update_current_frames", text="Update Camera Pose for Existing Keyframes")
        row.scale_y = 1.2

        # Separator
        layout.separator()
        
        # Live solving section
        col = layout.column()
        col.label(text="Live Solving:", icon="AUTO")
        
        # Live solve toggle button
        row = col.row()
        if settings.live_solve_enabled:
            live_icon = "PAUSE"
            live_text = "Stop Live Solve"
            live_color = True
        else:
            live_icon = "PLAY"
            live_text = "Start Live Solve"
            live_color = False
            
        live_op = row.operator("pnp.live_solve_toggle", text=live_text, icon=live_icon)
        row.scale_y = 1.8
        
        # Color the button differently when active
        if live_color:
            row.alert = True
        
        # Live solve status
        if settings.live_solve_enabled:
            status_row = col.row()
            status_row.label(text=f"Status: {settings.live_solve_status}", icon="INFO")
            
        # Live solve settings (only show when not active)
        if not settings.live_solve_enabled:
            box = col.box()
            box.label(text="Live Solve Settings:")
            
            settings_col = box.column(align=True)
            settings_col.prop(settings, "live_solve_sensitivity", text="Sensitivity")
            settings_col.prop(settings, "live_solve_update_rate", text="Update Rate (frames)")
            settings_col.prop(settings, "live_solve_auto_keyframe", text="Auto Keyframe")

        # Separator
        layout.separator()

        # Solve message
        row = layout.row()
        row.label(text=settings.pnp_solve_msg)

 

class TypeScriptExportSettings(bpy.types.Panel):
    """Collapsible sub-panel for TypeScript export settings"""

    bl_label = "TypeScript Export Settings"
    bl_idname = "CLIP_PT_TypeScript_Export_Settings"
    bl_space_type = "CLIP_EDITOR"
    bl_region_type = "TOOLS"
    bl_category = "Image Match"

    bl_parent_id = "CLIP_PT_Export"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(self, context):
        return current_image_initialised(context)

    def draw(self, context):
        layout = self.layout
        settings = context.scene.match_settings
        
        if settings.current_image_name not in settings.image_matches:
            return
            
        current_image = settings.image_matches[settings.current_image_name]
        camera = current_image.camera
        
        # Check if properties exist
        has_properties = all(prop in camera for prop in [
            "ts_export_id", "ts_export_name", "ts_export_category", 
            "ts_export_datetime", "ts_export_description", "ts_export_tags"
        ])
        
        if not has_properties:
            col = layout.column()
            col.label(text="TypeScript properties not initialized", icon="INFO")
            init_op = col.operator("camera.init_typescript_properties", 
                                  text="Initialize Properties", 
                                  icon="ADD")
            init_op.camera_name = camera.name
            return

        # Object metadata
        col = layout.column()
        col.prop(camera, '["ts_export_id"]', text="ID")
        col.prop(camera, '["ts_export_name"]', text="Name")
        col.prop(camera, '["ts_export_category"]', text="Category")
        col.prop(camera, '["ts_export_datetime"]', text="DateTime")
        
        col.separator()
        
        # Description and tags (reference image auto-filled from clip)
        col.prop(camera, '["ts_export_description"]', text="Description")
        col.prop(camera, '["ts_export_tags"]', text="Tags")

        col.separator()

        # Copy buttons
        col = layout.column(align=True)
        col.operator("imagematches.copy_typescript_object", 
                    text="Copy Current as TypeScript Object", 
                    icon="COPYDOWN")
        col.operator("imagematches.copy_all_typescript_objects", 
                    text="Copy All as TypeScript Objects", 
                    icon="DOCUMENTS")


class SceneCameraExportPanel(bpy.types.Panel):
    """Panel for scene camera TypeScript export in 3D view"""

    bl_label = "Camera TypeScript Export"
    bl_idname = "VIEW3D_PT_Camera_TypeScript_Export"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Tool"

    def draw(self, context):
        layout = self.layout
        
        col = layout.column()
        
        # Scene camera section
        col.label(text="Scene Camera:", icon="CAMERA_DATA")
        if context.scene.camera:
            camera = context.scene.camera
            
            # Check if properties exist
            has_properties = all(prop in camera for prop in [
                "ts_export_id", "ts_export_name", "ts_export_category", 
                "ts_export_datetime", "ts_export_reference_image",
                "ts_export_description", "ts_export_tags"
            ])
            
            if not has_properties:
                col.label(text=f"Camera: {camera.name}")
                init_op = col.operator("camera.init_typescript_properties", 
                                      text="Initialize Properties", 
                                      icon="ADD")
                init_op.camera_name = camera.name
            else:
                col.prop(camera, '["ts_export_id"]', text="ID")
                col.prop(camera, '["ts_export_name"]', text="Name") 
                col.prop(camera, '["ts_export_category"]', text="Category")
                col.prop(camera, '["ts_export_datetime"]', text="DateTime")
                col.prop(camera, '["ts_export_reference_image"]', text="Reference Image")
                col.prop(camera, '["ts_export_description"]', text="Description")
                col.prop(camera, '["ts_export_tags"]', text="Tags")
                
                col.separator()
                col.operator("view3d.copy_scene_camera_typescript", 
                            text="Copy Scene Camera", 
                            icon="COPYDOWN")
        else:
            col.label(text="No active scene camera", icon="ERROR")
            
        col.separator()
        
        # Selected camera section
        col.label(text="Selected Camera:", icon="OUTLINER_OB_CAMERA")
        if context.active_object and context.active_object.type == 'CAMERA':
            camera = context.active_object
            col.label(text=f"Active: {camera.name}")
            
            # Check if properties exist for selected camera
            has_properties = all(prop in camera for prop in [
                "ts_export_id", "ts_export_name", "ts_export_category", 
                "ts_export_datetime", "ts_export_reference_image",
                "ts_export_description", "ts_export_tags"
            ])
            
            if not has_properties:
                init_op = col.operator("camera.init_typescript_properties", 
                                      text="Initialize Properties", 
                                      icon="ADD")
                init_op.camera_name = camera.name
            else:
                col.operator("view3d.copy_selected_camera_typescript",
                            text="Copy Selected Camera", 
                            icon="COPYDOWN")
        else:
            col.label(text="No camera selected", icon="INFO")


class ExportPanel(bpy.types.Panel):
    """Panel for all image match export settings"""

    bl_label = "Export"
    bl_idname = "CLIP_PT_Export"
    bl_space_type = "CLIP_EDITOR"
    bl_region_type = "TOOLS"
    bl_category = "Image Match"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(self, context):
        return current_image_initialised(context)

    def draw(self, context):
        layout = self.layout
        settings = context.scene.match_settings

        row = layout.row(align=True)
        row.label(text="3D model :")
        row.prop(settings, "model", text="")

        row = layout.row(align=True)
        row.label(text="Export filepath :")
        row.prop(settings, "export_filepath", text="")

        row = layout.row(align=True)
        row.label(text="Export type :")
        row.prop(settings, "export_type", text="")

        row = layout.row()
        row.operator("imagematches.export_matches")