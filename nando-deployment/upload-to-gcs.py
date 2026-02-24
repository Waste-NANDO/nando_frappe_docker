#!/usr/bin/env python3
"""Upload ERPNext backup files to GCS and prune old backups."""
import argparse
import os

from google.cloud import storage


def upload_backups(backup_dir, bucket, site, timestamp, since):
    """Upload files from backup_dir that were modified after `since` (unix ts)."""
    uploaded = []
    for fname in sorted(os.listdir(backup_dir)):
        fpath = os.path.join(backup_dir, fname)
        if not os.path.isfile(fpath):
            continue
        if os.path.getmtime(fpath) < since:
            continue

        blob_name = f"{site}/{timestamp}/{fname}"
        bucket.blob(blob_name).upload_from_filename(fpath)
        uploaded.append(fname)
        print(f"  Uploaded: {blob_name}")

    for fname in os.listdir(backup_dir):
        fpath = os.path.join(backup_dir, fname)
        if os.path.isfile(fpath):
            os.remove(fpath)

    return uploaded


def prune_old_backups(bucket, site, keep):
    """Keep only the latest `keep` backup sets in GCS."""
    prefixes = set()
    for blob in bucket.list_blobs(prefix=f"{site}/"):
        parts = blob.name.split("/")
        if len(parts) >= 2 and parts[1]:
            prefixes.add(parts[1])

    sorted_prefixes = sorted(prefixes, reverse=True)
    to_prune = sorted_prefixes[keep:]

    if not to_prune:
        print(f"  {len(sorted_prefixes)} backup(s) in bucket, nothing to prune.")
        return

    for prefix in to_prune:
        print(f"  Pruning: {site}/{prefix}/")
        for blob in bucket.list_blobs(prefix=f"{site}/{prefix}/"):
            blob.delete()

    print(f"  Pruned {len(to_prune)} old backup(s).")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--site", required=True)
    p.add_argument("--bucket", required=True)
    p.add_argument("--key-file", required=True)
    p.add_argument("--timestamp", required=True)
    p.add_argument("--keep", type=int, default=10)
    p.add_argument("--backup-dir", required=True)
    p.add_argument("--since", type=float, required=True)
    args = p.parse_args()

    client = storage.Client.from_service_account_json(args.key_file)
    bucket = client.bucket(args.bucket)

    uploaded = upload_backups(
        args.backup_dir, bucket, args.site, args.timestamp, args.since
    )
    if not uploaded:
        print("WARNING: No backup files found to upload!")
        return

    print(
        f"Uploaded {len(uploaded)} file(s) to "
        f"gs://{args.bucket}/{args.site}/{args.timestamp}/"
    )

    prune_old_backups(bucket, args.site, args.keep)


if __name__ == "__main__":
    main()
