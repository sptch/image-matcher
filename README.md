# Image-Matcher

## A Blender Add-on for 2D-3D Image Matching and Camera Pose Estimation

Image-Matcher is a Blender add-on that allows matching multiple 2D images to a corresponding 3D model. This tool uses OpenCV's Perspective-n-Point solver to estimate camera intrinsics (e.g., focal length, distortion coefficients) and extrinsics (camera position and orientation) based on pairs of 2D and 3D points.

This project is a fork of [K-Meech's image-matcher](https://github.com/K-Meech/image-matcher), with improvements made by the Center for Spatial Technologies (CST) team. We extend our sincere gratitude to the original developers and contributors for their excellent work.

Originally builds on RT Studio's Camera Pnpoint Blender plugin: 
https://rtstudios.gumroad.com/l/camera_pnpoint / https://github.com/RT-studios/camera-pnpoint
Do consider buying their addon on gumroad/blender market to help support them making great Blender addons!

## Key Features and Improvements

Our fork builds upon the original plugin with several enhancements:

1. **Enhanced Animation Support**: Improved functionality for creating smooth camera animations between matched positions.
2. **Frame-by-Frame Solving**: Added capability to solve camera pose for each frame in a sequence.
3. **Keyframe Management**: New features to update camera poses for existing keyframes.

## Installation + Tutorials

- There's a full video tutorial of installation + image matching on youtube: https://www.youtube.com/watch?v=3gHtWkfxcvo
- For installation instructions, see: [Installation](./docs/installation.md)
- For a step by step tutorial of image matching, see: [Image matching tutorial](./docs/image-matching.md)

## Contributing

We welcome contributions to further improve this tool. Please submit issues or pull requests through GitHub.

---

For more information on the Perspective-n-Point process, see [OpenCV's documentation](https://docs.opencv.org/4.x/d5/d1f/calib3d_solvePnP.html).
