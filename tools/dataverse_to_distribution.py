from argparse import ArgumentParser
import json
from pathlib import Path
import sys
from ruamel.yaml import YAML

yaml=YAML()
yaml.default_flow_style = False
yaml.indent(sequence=4, offset=2)

package_dir = Path(__file__).parent.parent.resolve()


def read_json_file(file_path):
    """
    Load dictionary from json file
    """
    try:
        with open(file_path) as f:
            return json.load(f)
    except OSError as err:
        print("OS error: {0}".format(err))
    except:
        print("Unexpected error:", sys.exc_info()[0])
        raise


def add_obj_to_list(obj, arr, keys_to_match):
    """"""
    existing_obj = find_duplicate_object_in_list(
        list_to_search=arr,
        new_obj=obj,
        keys_to_match=keys_to_match,
    )
    if not existing_obj:
        arr.append(obj)
        return obj
    else:
        return existing_obj


def find_duplicate_object_in_list(
    list_to_search: list, new_obj: object, keys_to_match
):
    """"""
    existing_objects = list_to_search
    for key in keys_to_match:
        existing_objects = [
            obj
            for obj in existing_objects
            if (key in new_obj) and (key in obj) and (obj[key] == new_obj[key])
        ]

    if not bool(existing_objects):
        return None
    else:
        return existing_objects[0]


def get_parts(dv_files, schema_files):
    has_part = []
    qualified_part = []
    # for each file:
    for f in dv_files:
        fname = f["label"]
        fpath = f["label"] if "directoryLabel" not in f else f["directoryLabel"] + "/" + f["label"]
        fdata = f["dataFile"]
        # Let's start with the file:
        file_obj = {
            "id": "exthisdsver:./" + fpath,
            # "id": fdata["md5"],
            "byte_size": fdata["filesize"],
            "checksum": [{
                "algorithm": "md5",
                "digest": fdata["md5"]
            }],
            "download_url": ["https://dataverse.nl/api/access/datafile/" + str(fdata["id"])],
            "media_type": fdata["contentType"],
        }
        # all fileobjects have to be added to the main has_part list
        file_obj = add_obj_to_list(
            obj=file_obj,
            arr=has_part,
            keys_to_match=[
                "id",
            ]
        )
        # If the file data DOES NOT have "directoryLabel" field, it is a root-level file
        # which has to be added to the root-level qualified_part list
        if "directoryLabel" not in f:
            qualified_file_obj = add_obj_to_list(
                obj={
                    "entity": file_obj["id"],
                    "name": f["label"],
                },
                arr=qualified_part,
                keys_to_match=[
                    "entity",
                    "name"
                ]
            )
            # nothing left to do for this file
            continue
        # If the file data DOES have a "directoryLabel" field, it is a file inside a directory
        # (or a tree of directories). We need to loop through directory tree (i.e. parts in path up
        # to and  the file's parent) and create distribution objects and their relations for each directory,
        # and distribution objects and their relations for each file, and add all to the relevant lists.
        fdir = Path(f["directoryLabel"])
        fdir_parts = list(fdir.parts)
        for idx, dirname in enumerate(fdir_parts):
            current_path = f"{'/'.join(fdir_parts[:idx+1])}/"
            # All sub-distributions (i.e. directories) have to be added to the top-level distribution["has_part"] (if it doesn't exist)
            # All sub-distribution entities have to be added to their parent's filecontainerobject["qualified_part"] (if it doesn't exist)
            container_obj = add_obj_to_list(
                obj={
                    "id": "exthisdsver:./" + current_path,
                    "qualified_part": []
                },
                arr=has_part,
                keys_to_match=[
                    "id",
                ]
            )
            # Then:
            # 1. if it's the root directory of the current file (and not parent):
            # - add qualified part to distribution["qualified_part"] (if it doesn't exist)
            # 2. if it's NOT the root NOR parent directory of the current file: 
            # - add qualified part to distribution["has_part"][current_dir] (if it doesn't exist)
            # 3. if it's the file's parent directory:
            # - add qualified part to distribution["has_part"][current_dir] (if it doesn't exist)
            # - add file relation as qualified part to distribution["has_part"][current_dir] (if it doesn't exist)
            # 1:
            if idx == 0:
                # IS rootdir
                qualified_obj = add_obj_to_list(
                    obj={
                        "entity": "exthisdsver:./" + current_path,
                        "name": dirname,
                    },
                    arr=qualified_part,
                    keys_to_match=[
                        "entity",
                        "name"
                    ]
                )
            # 3:
            else:
                # any other dir
                qualified_obj = add_obj_to_list(
                    obj={
                        "entity": "exthisdsver:./" + current_path,
                        "name": dirname,
                    },
                    arr=previous_container_obj["qualified_part"],
                    keys_to_match=[
                        "entity",
                        "name"
                    ]
                )
            # with file's parent dir, add qualified file relation to container object
            if idx == len(fdir_parts) - 1:
                qualified_file_obj = add_obj_to_list(
                    obj={
                        "entity": "exthisdsver:./" + fpath,
                        "name": f["label"],
                    },
                    arr=container_obj["qualified_part"],
                    keys_to_match=[
                        "entity",
                        "name"
                    ]
                )
            previous_container_obj = container_obj

    return has_part, qualified_part


if __name__ == "__main__":
    # load arguments
    parser = ArgumentParser()
    parser.add_argument(
        "jsonfile", type=str, help="Path to the dataverse-json export",
    )
    parser.add_argument(
        "schema_file", type=str, help="Path to the schemaorg-jsonld export",
    )
    args = parser.parse_args()
    # load files into dicts
    json_obj = read_json_file(Path(args.jsonfile))
    schema_obj = read_json_file(Path(args.schema_file))
    

    # ---------------------------
    # Relations to contextual entities
    # i.e. describe the dataset contextually
    # ---------------------------

    # First list agents:
    agents = [
        # Stephan Heunis
        dict(
            id="exthisds:#" + schema_obj["creator"][0]["givenName"] + schema_obj["creator"][0]["familyName"],
            meta_type="dldist:Person",
            name=schema_obj["creator"][0]["givenName"] + ' ' + schema_obj["creator"][0]["familyName"],
            identifier=[
                {
                    "schema_agency": "https://orcid.org",
                    "notation": schema_obj["creator"][0]["identifier"].replace("https://orcid.org/", ""),
                },
            ],              
            affiliation=["exthisds:#" + schema_obj["creator"][0]["affiliation"]["name"].replace(" ", "")],
            same_as=[
                schema_obj["creator"][0]["identifier"]
            ],
        ),
        # Eindhoven University
        dict(
            id="exthisds:#" + schema_obj["creator"][0]["affiliation"]["name"].replace(" ", ""),
            meta_type="dldist:Organization",
            name=schema_obj["creator"][0]["affiliation"]["name"],
            identifier=[
                {
                    "schema_agency": "https://ror.org",
                    "notation": "02c2kyt77",
                },
                {
                    "schema_agency": "https://www.wikidata.org/wiki",
                    "notation": "Q280824",
                },
            ],
            same_as=[
                "https://ror.org/02c2kyt77"
                "https://www.wikidata.org/wiki/Q280824"
            ],
        ),
    ]
    # Then publications
    # note: these publications aren't contained in the dataverse metadata
    publications = [
        dict(
            id="exthisds:#data_paper",
            meta_type="dlsdd:Publication",
            notation="Heunis S, Breeuwer M, Caballero-Gaudes C et al. rt-me-fMRI: a task and resting state dataset for real-time, multi-echo fMRI methods development and validation [version 1; peer review: 1 approved, 1 approved with reservations]. F1000Research 2021, 10:70 (https://doi.org/10.12688/f1000research.29988.1)",
            date_published="2021-02-04",
            identifier=[
                {
                    "schema_agency": "https://doi.org",
                    "notation": "10.12688/f1000research.29988.1",
                },
            ],
            qualified_attribution=[
                {
                    "agent":agents[0]["id"],
                    "had_role": [
                        "marcrel:aut",
                        "marcrel:col",
                        "marcrel:cre"
                    ],
                }
            ]
        ),
        dict(
            id="exthisds:#methods_paper",
            meta_type="dlsdd:Publication",
            notation="S. Heunis, M. Breeuwer, C. Caballero-Gaudes, L. Hellrung, W. Huijbers, J.F. Jansen, R. Lamerichs, S. Zinger, A.P. Aldenkamp. The effects of multi-echo fMRI combination and rapid T*-mapping on offline and real-time BOLD sensitivity. NeuroImage, 238 (2021), Article 118244, 10.1016/j.neuroimage.2021.118244",
            date_published="2021-06-11",
            identifier=[
                {
                    "schema_agency": "https://doi.org",
                    "notation": "10.1016/j.neuroimage.2021.118244",
                },
            ],
            qualified_attribution=[
                {
                    "agent":agents[0]["id"],
                    "had_role": [
                        "marcrel:aut",
                    ],
                }
            ],
        )
    ]
    # Then dataset version relation
    dataset_version = dict(
        id="exthisdsver:#",
        meta_type="dldist:Resource",
        date_modified=schema_obj["dateModified"],
        description=schema_obj["description"],
        is_version_of="exthisds:#",
        keyword=schema_obj["keywords"],
        landing_page=schema_obj["identifier"], # doi of the dataset
        name="dataverse-rtmefmri",
        title=schema_obj["name"],
        version=str(json_obj["datasetVersion"]["versionNumber"]) + "." + str(json_obj["datasetVersion"]["versionMinorNumber"]), # jsonld only gives major version
        same_as=[
            schema_obj["identifier"],
        ],
        identifier=[
            {
                "schema_agency": "https://doi.org",
                "notation": schema_obj["identifier"].replace("https://doi.org/", ""),
            },
        ],
        qualified_attribution=[
            dict(
                agent=agents[0]["id"],
                had_role=[
                    "marcrel:aut",
                    "marcrel:col",
                    "marcrel:cre"
                ],
            ),
            dict(
                agent=agents[1]["id"],
                had_role=[
                    "marcrel:sht", # Supporting host
                ],
            )
        ],
        qualified_relation=[
            # data paper
            dict(
                had_role=[
                    "CiTO:isDocumentedBy",
                    "CiTO:citesAsAuthority",
                ],
                entity=[publications[0]["id"]]
            ),
            # methods paper
            dict(
                had_role=[
                    "CiTO:isCitedAsDataSourceBy",
                ],
                entity=[publications[1]["id"]]
            ),
            # TODO: include grants with "had_role: schema:funding"
        ],
    )
    # Then license
    license = dict(
        id="exthisds:#humanhealthdatalicense",
        meta_type="dldist:LicenseDocument",
        same_as=[
            schema_obj["license"],
        ],
        license_text=json_obj["datasetVersion"]["termsOfUse"]
    )
    # Then put the relations together in a list
    relation = [dataset_version] + agents + publications + [license]
    # TODO: include study activity and study participants
    # TODO: include access

    # ---------------------------
    # Then build the distribution
    # ---------------------------

    # Distribution and some base properties, relations, and (qualified) parts
    has_part, qualified_part = get_parts(json_obj["datasetVersion"]["files"], schema_obj["distribution"])
    distribution = dict(
        id="exthisdsver:.",
        conforms_to=[
            "https://bids-specification.readthedocs.io/en/v1.6.0"
        ],
        license=license["id"],
        is_distribution_of="exthisdsver:#",
        was_attributed_to=[
            agents[0]["id"],
            agents[1]["id"],
        ],
        relation=relation,
        qualified_part=qualified_part,
        has_part=has_part,
    )
    # 5. Write to yaml file
    outfile = 'Distribution-dataverse-rtmefmri.yaml'
    with open(outfile, 'w') as outf:
        yaml.dump(distribution, outf)