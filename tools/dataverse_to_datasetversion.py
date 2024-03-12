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
    Load content from catalog metadata file for current node
    """
    try:
        with open(file_path) as f:
            return json.load(f)
    except OSError as err:
        print("OS error: {0}".format(err))
    except:
        print("Unexpected error:", sys.exc_info()[0])
        raise

fields = [
    "name",
    "title",
    "description",
    "landing_page",
    "version",
    "modified",
    "keyword",
    "identifier",
    "custom_licenses",
    "license",
    "was_attributed_to",
    "qualified_attribution",
    "relation",
    "qualified_relation",
    "has_part"
    "distribution",
    # access?
]

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
        fdata = f["dataFile"]
        # Let's start with the file:
        file_obj = {
            "meta_type": "dlco:DigitalDocumentObject",
            "meta_code": fdata["md5"],
            "byte_size": fdata["filesize"],
            "checksum": {
                "algorithm": "md5",
                "digest": fdata["md5"]
            },
            "download_url": "https://dataverse.nl/api/access/datafile/" + str(fdata["id"])
        }

        # all fileobjects have to be added to the main has_part list
        file_obj = add_obj_to_list(
            obj=file_obj,
            arr=has_part,
            keys_to_match=[
                "meta_type",
                "meta_code"
            ]
        )
        # If the file data DOES NOT have "directoryLabel" field, it is a root-level file
        # which has to be added to the root-level qualified_part list
        if "directoryLabel" not in f:
            qualified_file_obj = add_obj_to_list(
                obj={
                    "relation": fdata["md5"],
                    "name": f["label"],
                },
                arr=qualified_part,
                keys_to_match=[
                    "relation",
                    "name"
                ]
            )
            # nothing left to do for this file
            continue
            
        # If the file data DOES have a "directoryLabel" field, it is a file inside a directory
        # (or a tree of directories). We need to loop through directory tree (i.e. parts in path up
        # to the file's parent) and create filecontainerobjects and their relations for each directory,
        # and digitalobjects and their relations for each file, and add all to the relevant lists.
        fdir = Path(f["directoryLabel"])
        fdir_parts = list(fdir.parts)
        for idx, dirname in enumerate(fdir_parts):

            current_path = f"{'/'.join(fdir_parts[:idx+1])}/"

            # All filecontainerobjects (i.e. directories) have to be added to distribution["has_part"] (if it doesn't exist)
            # All filecontainerobject relations have to be added to their parent's filecontainerobject["qualified_part"] (if it doesn't exist)
            container_obj = add_obj_to_list(
                obj={
                    "meta_type": "dlco:FileContainerObject",
                    "meta_code": current_path,
                    "qualified_part": []
                },
                arr=has_part,
                keys_to_match=[
                    "meta_type",
                    "meta_code"
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
                        "relation": current_path,
                        "name": dirname,
                    },
                    arr=qualified_part,
                    keys_to_match=[
                        "relation",
                        "name"
                    ]
                )
            # 3:
            else:
                # any other dir
                qualified_obj = add_obj_to_list(
                    obj={
                        "relation": current_path,
                        "name": dirname,
                    },
                    arr=previous_container_obj["qualified_part"],
                    keys_to_match=[
                        "relation",
                        "name"
                    ]
                )

            # with file's parent dir, add qualified file relation to container object
            if idx == len(fdir_parts) - 1:

                qualified_file_obj = add_obj_to_list(
                    obj={
                        "relation": fdata["md5"],
                        "name": f["label"],
                    },
                    arr=container_obj["qualified_part"],
                    keys_to_match=[
                        "relation",
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
    
    # ------------------------------
    # construct dataset-version dict
    # ------------------------------

    # 1. (Qualified) Attributions
    was_attributed_to = [
        # Stephan Heunis
        dict(
            meta_type="dlco:ResearchContributorObject",
            meta_code=schema_obj["creator"][0]["givenName"] + schema_obj["creator"][0]["familyName"],
            name=schema_obj["creator"][0]["givenName"] + ' ' + schema_obj["creator"][0]["familyName"],
            orcid=schema_obj["creator"][0]["identifier"].replace("https://orcid.org/", ""),
            affiliation=schema_obj["creator"][0]["affiliation"]["name"],
        ),
        # Eindhoven University
        dict(
            meta_type="dlco:OrganizationObject",
            meta_code="TUE",
            name=schema_obj["creator"][0]["affiliation"]["name"],
        ),
    ]
    qualified_attribution = [
        dict(
            agent=was_attributed_to[0]["meta_code"],
            had_role=[
                "marcrel:aut",
                "marcrel:col",
                "marcrel:cre"
            ],
        ),
        dict(
            agent=was_attributed_to[1]["meta_code"],
            had_role=[
                "marcrel:sht",
            ],
        )
    ]
    # 2. (Qualified) Relations 
    # note: these publications aren't contained in the dataverse metadata
    relation = [
        dict(
            meta_type="dlco:PublicationObject",
            meta_code="data_paper",
            citation="Heunis S, Breeuwer M, Caballero-Gaudes C et al. rt-me-fMRI: a task and resting state dataset for real-time, multi-echo fMRI methods development and validation [version 1; peer review: 1 approved, 1 approved with reservations]. F1000Research 2021, 10:70 (https://doi.org/10.12688/f1000research.29988.1)",
            doi="https://doi.org/10.12688/f1000research.29988.1",
        ),
        dict(
            meta_type="dlco:PublicationObject",
            meta_code="methods_paper",
            citation="S. Heunis, M. Breeuwer, C. Caballero-Gaudes, L. Hellrung, W. Huijbers, J.F. Jansen, R. Lamerichs, S. Zinger, A.P. Aldenkamp. The effects of multi-echo fMRI combination and rapid T*-mapping on offline and real-time BOLD sensitivity. NeuroImage, 238 (2021), Article 118244, 10.1016/j.neuroimage.2021.118244",
            doi="https://doi.org/10.1016/j.neuroimage.2021.118244",
        )

    ]
    qualified_relation = [
        # data paper
        dict(
            had_role=[
                "CiTO:isDocumentedBy",
                "CiTO:citesAsAuthority",
            ],
            entity=relation[0]["meta_code"]
        ),
        # methods paper
        dict(
            had_role=[
                "CiTO:isCitedAsDataSourceBy",
            ],
            entity=relation[1]["meta_code"]
        ),
    ]
    # 3. Distribution and (Qualified) Parts
    has_part, qualified_part = get_parts(json_obj["datasetVersion"]["files"], schema_obj["distribution"])
    distribution = dict(
        meta_type="dlco:FileContainerObject",
        meta_code="./",
        license="customlicenses:humanhealthdata",
        has_part=has_part,
        qualified_part=qualified_part,
    )
    # 4. Construct final dataset-version dictionary
    dsversion_obj = dict(
        name="dataverse-rtmefmri",
        title=schema_obj["name"],
        description=schema_obj["description"],
        landing_page=schema_obj["identifier"], # doi of the dataset
        version=str(json_obj["datasetVersion"]["versionNumber"]) + "." + str(json_obj["datasetVersion"]["versionMinorNumber"]), # jsonld only gives major version
        modified=schema_obj["dateModified"],
        keyword=schema_obj["keywords"],
        identifier=[schema_obj["identifier"]],
        custom_licenses={
            "customlicenses:humanhealthdata": dict(
                identifier=schema_obj["license"],
                license_text=json_obj["datasetVersion"]["termsOfUse"]
            )
        },
        license="customlicenses:humanhealthdata",
        was_attributed_to=was_attributed_to,
        qualified_attribution=qualified_attribution,
        relation=relation,
        qualified_relation=qualified_relation,
        distribution=distribution,
    )
    # 5. Write to yaml file
    outfile = package_dir / 'src' / 'examples' / 'dataset-version' / 'DatasetVersionObject-dataverse-rtmefmri.yaml'
    with open(outfile, 'w') as outf:
        yaml.dump(dsversion_obj, outf)