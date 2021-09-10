import blenderproc as bproc
from blenderproc.python.utility.SetupUtility import SetupUtility
SetupUtility.setup([])

import argparse

from blenderproc.python.writer.WriterUtility import WriterUtility
from blenderproc.python.utility.Initializer import Initializer
from blenderproc.python.types.LightUtility import Light
from blenderproc.python.utility.MathUtility import MathUtility

from blenderproc.python.renderer.RendererUtility import RendererUtility

parser = argparse.ArgumentParser()
parser.add_argument('camera', nargs='?', default="examples/advanced/motion_blur_rolling_shutter/camera_positions", help="Path to the camera file")
parser.add_argument('scene', nargs='?', default="examples/resources/scene.obj", help="Path to the scene.obj file")
parser.add_argument('output_dir', nargs='?', default="examples/advanced/motion_blur_rolling_shutter/output", help="Path to where the final files will be saved ")
args = parser.parse_args()

Initializer.init()

# load the objects into the scene
objs = bproc.loader.load_obj(args.scene)

# define a light and set its location and energy level
light = Light()
light.set_type("POINT")
light.set_location([5, -5, 5])
light.set_energy(1000)

# define the camera intrinsics
bproc.camera.set_intrinsics_from_blender_params(1, 512, 512, lens_unit="FOV")

# read the camera positions file and convert into homogeneous camera-world transformation
with open(args.camera, "r") as f:
    for line in f.readlines():
        line = [float(x) for x in line.split()]
        position, euler_rotation = line[:3], line[3:6]
        matrix_world = MathUtility.build_transformation_mat(position, euler_rotation)
        bproc.camera.add_camera_pose(matrix_world)

# Enable motion blur and rolling shutter
RendererUtility.enable_motion_blur(
    motion_blur_length=0.8,
    rolling_shutter_type="TOP",
    rolling_shutter_length=0.05
)

# activate distance rendering
RendererUtility.enable_distance_output()
# set the amount of samples, which should be used for the color rendering
RendererUtility.set_samples(350)

# render the whole pipeline
data = RendererUtility.render()

# write the data to a .hdf5 container
WriterUtility.save_to_hdf5(args.output_dir, data)