from blenderproc.python.SetupUtility import SetupUtility
SetupUtility.setup([])

from blenderproc.python.camera.CameraUtility import CameraUtility
from blenderproc.python.MathUtility import MathUtility
from blenderproc.python.sampler.SuncgPointInRoomSampler import SuncgPointInRoomSampler
from blenderproc.python.LabelIdMapping import LabelIdMapping
from blenderproc.python.types.MeshObjectUtility import MeshObject
from blenderproc.python.MaterialLoaderUtility import MaterialLoaderUtility
from blenderproc.python.renderer.SegMapRendererUtility import SegMapRendererUtility

from blenderproc.python.object.ObjectReplacer import ObjectReplacer
from blenderproc.python.Utility import Utility
from blenderproc.python.camera.CameraValidation import CameraValidation
from blenderproc.python.loader.SuncgLoader import SuncgLoader
from blenderproc.python.loader.ObjectLoader import ObjectLoader
from blenderproc.python.filter.Filter import Filter
from blenderproc.python.lighting.SuncgLighting import SuncgLighting

from blenderproc.python.writer.WriterUtility import WriterUtility
from blenderproc.python.Initializer import Initializer

from blenderproc.python.renderer.RendererUtility import RendererUtility
import numpy as np
from mathutils import Euler
import argparse
import os

parser = argparse.ArgumentParser()
parser.add_argument('house', help="Path to the house.json file of the SUNCG scene to load")
parser.add_argument('object_path', help='Path to the chair object which will be used to replace others.')
parser.add_argument('output_dir', nargs='?', default="examples/datasets/suncg_with_object_replacer/output",
                    help="Path to where the final files, will be saved")
args = parser.parse_args()

Initializer.init()

# load the objects into the scene
label_mapping = LabelIdMapping.from_csv(Utility.resolve_path(os.path.join('resources', 'id_mappings', 'nyu_idset.csv')))
objs = SuncgLoader.load(args.house, label_mapping)

# replace some objects with others

chair_obj = ObjectLoader.load(args.object_path)
if len(chair_obj) != 1:
    raise Exception(f"There should only be one chair object not: {len(chair_obj)}")
chair_obj = chair_obj[0]


def relative_pose_sampler(obj):
    # Sample random rotation and apply it to the objects pose
    obj.blender_obj.rotation_euler.rotate(Euler((0, 0, np.random.uniform(0.0, 6.283185307))))


replace_ratio = 1.0
ObjectReplacer.replace_multiple(
    objects_to_be_replaced=Filter.by_cp(objs, "coarse_grained_class", "chair"),
    objects_to_replace_with=[chair_obj],
    ignore_collision_with=Filter.by_cp(objs, "type", "Floor"),
    replace_ratio=replace_ratio,
    copy_properties=True,
    relative_pose_sampler=relative_pose_sampler
)

# some of the objects won't be valid anymore
objs = [obj for obj in objs if obj.is_valid()]

# makes Suncg objects emit light
SuncgLighting.light()

# Init sampler for sampling locations inside the loaded suncg house
point_sampler = SuncgPointInRoomSampler(objs)
# Init bvh tree containing all mesh objects
bvh_tree = MeshObject.create_bvh_tree_multi_objects([o for o in objs if isinstance(o, MeshObject)])

poses = 0
tries = 0
while tries < 10000 and poses < 5:
    # Sample point inside house
    height = np.random.uniform(0.5, 2)
    location, _ = point_sampler.sample(height)
    # Sample rotation (fix around X and Y axis)
    euler_rotation = np.random.uniform([1.2217, 0, 0], [1.2217, 0, 6.283185307])
    cam2world_matrix = MathUtility.build_transformation_mat(location, euler_rotation)

    # Check that obstacles are at least 1 meter away from the camera and make sure the view interesting enough
    if CameraValidation.perform_obstacle_in_view_check(cam2world_matrix, {"min": 1.0},
                                                       bvh_tree) and CameraValidation.scene_coverage_score(
            cam2world_matrix) > 0.4:
        CameraUtility.add_camera_pose(cam2world_matrix)
        poses += 1
    tries += 1

# activate normal and distance rendering
RendererUtility.enable_normals_output()
RendererUtility.enable_distance_output()
MaterialLoaderUtility.add_alpha_channel_to_textures(blurry_edges=True)

# render the whole pipeline
data = RendererUtility.render()

data.update(SegMapRendererUtility.render(Utility.get_temporary_directory(), Utility.get_temporary_directory(), "class",
                                         use_alpha_channel=True))

# write the data to a .hdf5 container
WriterUtility.save_to_hdf5(args.output_dir, data)
