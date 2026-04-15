### Purpose
- Convert a Zeiss .czi file, or a folder of .czi files to OME-Zarr image(s).

### Outputs
- One or more OME-Zarr images.

### Limitations
- This task has been tested on a limited set of acquisitions. It may not work on all Zeiss .czi acquisitions.
- HCS plate conversion is not yet supported — only standalone images and folders of standalone images.
- See below for more detailed input expectations.

### Expected inputs
The following input layouts are supported. (The names in curly braces `{}` can be freely chosen by the user.)

- Single file acquisition
	- acquisition path input:
		```text
		.../{filename}.czi
		```
	- output: single OME-Zarr image

- Folder of single file acquisitions
	- acquisition path input:
		```text
		.../{folder}
		----/{filename1}.czi
		----/{filename2}.czi
		...
		```
	- output: multiple OME-Zarr images
