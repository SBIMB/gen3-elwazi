## Logical Volumes with Linux
### Adding A Logical Volume
There exists a volume group called `chipster` which has about `3.6TB` of available storage space. The physical volume corresponding to this volume group is `/dev/sdc1`.   

Our goal is to create a logical volume called `minio_lv` with size or capacity of `400GB`. The `minio_lv` will be partitioned into four separate drives (of `100GB` each), in accordance with setting up a MinIO instance that has the deployment strategy of [single-node multi-drive](https://min.io/docs/minio/linux/operations/install-deploy-manage/deploy-minio-single-node-multi-drive.html).

The volume groups can be listed with the command:
```bash
sudo pvs
```
and a more detailed description of a particular volume group, in this case `chipster`, can be seen with:
```bash
sudo vgdisplay chipster
```
![Chipster Volume Group Details](/public/assets/images/vgdisplay-chipster.png "Chipster Volume Group Details")    

We use the `lvcreate` command to create a new logical volume. The command is as follows:
```bash
sudo lvcreate -L 400G -n minio_lv chipster
```
The status of the newly created logical volume can be seen with:
```bash
sudo lvs /dev/chipster/minio_lv
```
and a more detailed description of the logical volume can be seen with:
```bash
sudo lvdisplay /dev/chipster/minio_lv
```
![MinIO Logical Volume](/public/assets/images/minio-lv.png "MinIO Logical Volume")    

Our next task is to format the logical volume with a particular file system. For large files, it is recommended to use **XFS**, since it can perform input and output simultaneously. It is also the recommended file system by the MinIO developers. The following command will format the logical volume with the **XFS** file system:
```bash
sudo mkfs.xfs /dev/chipster/minio_lv
```
Now we'd like to mount this file system to a directory on our Linux machine. First, we create a new directory called `minio`,
```bash
sudo mkdir -p /mnt/data/minio
sudo chown minio-user /mnt/data/minio
```
We mount the file system as follows:
```bash
sudo mount /dev/chipster/minio_lv /mnt/data/minio
```
![Mounted Chipster Tools Directory](/public/assets/images/mounted-chipster-tools-directory.png "Mounted Chipster Tools Directory")     

Now we'd like to mount this file system to four directories or drives on our Linux machine. We need to name these drives sequentially, i.e. `drive1`, `drive2`, `drive3`, and `drive4`. First, we create a new directory called `chipster`,
```bash
sudo mkdir -p /mnt/data/minio/drive{1..4}
sudo chown minio-user /mnt/data/minio/drive{1..4}
```
To ensure that the file system does _not_ get unmounted when the system is rebooted, we should update the `/etc/fstab` configuration file with the relevant data in the format:
```bash
<file system> <mount point> <type> <options> <dump> <pass>
```
We can get some of this information by running the command:
```
df -kHT
```
and looking at the different columns in the output table. In our case above, the `/etc/fstab` should be updated with the following:
```bash
/dev/mapper/chipster-chipster_tools_lv /mnt/data/chipster xfs defaults 0 2
```
The `dump` parameter is used by the dump utility to decide if the file system should be backed up. The key-value pairs are:   

- 0: Do not back up the file system
- 1: Back up the file system during `dump`   

The `pass` parameter determines the order in which the file systems get checked during boot or reboot. The key-value pairs are:   

- 0: Do not check the file system
- 1: Check file system first (common for root file systems)
- 2: Check file system after the root file system   

If ever required, we can extend the size of the logical volume by using the `lvextend` command. We can extend it by a percentage (let's say `50%`) of the free space inside the volume group, e.g.
```bash
lvextend -l +50%FREE /dev/chipster/chipster_tools_lv
```
For session storage (i.e., when Chipster jobs are being run), we should create a directory called `/mnt/data/chipster/file-storage` and ensure that this path is specified in the relevant pod or deployment manifest (the `file-storage` pod).

### Removing A Logical Volume
To remove a logical volume from a volume group, the first step is to unmount the file system with the `umount` command:
```bash
umount /chipster_tools
```
The `/etc/fstab` file can be checked to verify that an entry to automatically mount the file system doesn't exist. If one exists, the entry should be removed and the changes saved.   

Now the logical volume can be removed using the `lvremove` command:
```bash
lvremove vg0/myvol
```
To verify that the removal was successful, check the output of:
```bash
sudo vgs
```
The storage that was assigned to the logical volume should be made available to the volume group.
