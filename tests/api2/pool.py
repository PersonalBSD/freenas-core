#!/usr/bin/env python3.6

import pytest
import sys
import os
import time
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import POST, GET, DELETE, SSH_TEST, send_file
from auto_config import ip, user, password, pool_name, disk1, disk2

dataset = f"{pool_name}/test_pool"
dataset_url = dataset.replace('/', '%2F')
dataset_path = os.path.join("/mnt", dataset)

IMAGES = {}


def expect_state(job_id, state):
    for _ in range(60):
        job = GET(f"/core/get_jobs/?id={job_id}").json()[0]
        if job["state"] in ["WAITING", "RUNNING"]:
            time.sleep(1)
            continue
        if job["state"] == state:
            return job
        else:
            assert False, job
    assert False, job


def test_01_get_pool():
    results = GET("/pool/")
    assert results.status_code == 200, results.text


def test_02_creating_a_pool():
    payload = {
        "name": pool_name,
        "encryption": False,
        "topology": {
            "data": [
                {"type": "STRIPE", "disks": [disk1, disk2]}
            ],
        }
    }
    results = POST("/pool/", payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    expect_state(job_id, "SUCCESS")


def test_03_create_dataset():
    result = POST("/pool/dataset/", {"name": dataset})
    assert result.status_code == 200, result.text


@pytest.mark.parametrize('image', ["msdosfs", "msdosfs-nonascii", "ntfs"])
def test_04_setup_function(image):
    zf = os.path.join(os.path.dirname(__file__), "fixtures", f"{image}.gz")
    destination = f"/tmp/{image}.gz"
    send_results = send_file(zf, destination, user, None, ip)
    assert send_results['result'] is True, send_results['output']

    cmd = f"gunzip -f /tmp/{image}.gz"
    gunzip_results = SSH_TEST(cmd, user, password, ip)
    assert gunzip_results['result'] is True, gunzip_results['output']

    cmd = f"mdconfig -a -t vnode -f /tmp/{image}"
    mdconfig_results = SSH_TEST(cmd, user, password, ip)
    assert mdconfig_results['result'] is True, mdconfig_results['output']
    IMAGES[image] = mdconfig_results['output'].strip()


def test_06_import_msdosfs():
    payload = {
        "device": f"/dev/{IMAGES['msdosfs']}s1",
        "fs_type": "msdosfs",
        "fs_options": {},
        "dst_path": dataset_path,
    }
    results = POST("/pool/import_disk/", payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    expect_state(job_id, "SUCCESS")


def test_07_look_if_Directory_slash_File():
    cmd = f'test -f {dataset_path}/Directory/File'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']


def test_08_import_nonascii_msdosfs_fails():
    payload = {
        "device": f"/dev/{IMAGES['msdosfs-nonascii']}s1",
        "fs_type": "msdosfs",
        "fs_options": {},
        "dst_path": dataset_path,
    }
    results = POST("/pool/import_disk/", payload)
    assert results.status_code == 200, results.text

    job_id = results.json()

    job = expect_state(job_id, "FAILED")

    assert job["error"] == "rsync failed with exit code 23", job


def test_09_look_if_Directory_slash_File():
    cmd = f'test -f {dataset_path}/Directory/File'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']


def test_10_import_nonascii_msdosfs():
    payload = {
        "device": f"/dev/{IMAGES['msdosfs-nonascii']}s1",
        "fs_type": "msdosfs",
        "fs_options": {"locale": "ru_RU.UTF-8"},
        "dst_path": dataset_path,
    }
    results = POST("/pool/import_disk/", payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    expect_state(job_id, "SUCCESS")


def test_08_look_if_Каталог_slash_Файл():
    cmd = f'test -f {dataset_path}/Каталог/Файл'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']


def test_11_import_ntfs():
    payload = {
        "device": f"/dev/{IMAGES['ntfs']}s1",
        "fs_type": "ntfs",
        "fs_options": {},
        "dst_path": dataset_path,
    }
    results = POST("/pool/import_disk/", payload)
    assert results.status_code == 200, results.text

    job_id = results.json()

    expect_state(job_id, "SUCCESS")


def test_12_look_if_Каталог_slash_Файл():
    cmd = f'test -f {dataset_path}/Каталог/Файл'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']


@pytest.mark.parametrize('image', ["msdosfs", "msdosfs-nonascii", "ntfs"])
def test_13_stop_image_with_mdconfig(image):
    cmd = f"mdconfig -d -u {IMAGES[image]}"
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']

    cmd = f"rm -fv /tmp/{image}.gz"
    gunzip_results = SSH_TEST(cmd, user, password, ip)
    assert gunzip_results['result'] is True, gunzip_results['output']

    cmd = f"rm -rfv /tmp/{image}"
    rm_results = SSH_TEST(cmd, user, password, ip)
    assert rm_results['result'] is True, rm_results['output']


def test_14_delete_dataset():
    results = DELETE(f"/pool/dataset/id/{dataset_url}/")
    assert results.status_code == 200, results.text
