[Darktable](http://www.darktable.org) sqlite3 database management from
the command line!

Tested only with version 1.0+1830~g39f5af7 ([git](http://github.com/darktable-org/darktable)).  Should work on other versions as long as there are no
changes to the following tables:  film_rolls, history, images, meta_data,
tags and tagged_images.

Note, I had initially thought that in addition to updating the Darktable
database I would need to make the equivalent changes in the .xmp sidecar
file.  This does not appear to be the case -- in all my testing it appears
as though the Darktable will update the sidecar file on startup if it 
detects any changes in the database. So it appears I do not need to worry
about the sidecar - I can just make the changes I want to the database 
and then let Darktable update the sidecar on next start.

```
$ dt --help
usage: dt [-h] [-d DTDB] [--no-backup] <command> <parameter> [<parameter> ...]

Darktable filmroll/image/metadata maintenance:

mv <src> <dest>                                  rename film roll or image
query <dir|file> [ <dir|file> ... ]              dump details of a film roll or image (best on 132+ column term)
scan <dir|file> [ <dir}|file> ... ]              just report if the object does not exist in the db - 
                                                 .xmp and .meta extensions will be stripped before the check
set <image> <var> <val> [ <var> <val> ... ]      set a variable for a specific file

For the 'set' command, the valid var's are:
image table:
    datetime_taken         "YYYY:MM:DD HH:MM:SS"
    caption                "text"
    description            "text"
    license                "text"
    longitude              float (-180.0 to +180.0, positive E)
    latitude               float (-90.0 to +90.0, positive N)
                           Note: To convert degrees minutes seconds to a float: 
                                       f = degrees + ( minutes + seconds/60. ) / 60.
                                 and change sign if W or S.
meta_data table:
    creator                "text"
    publisher              "text"
    title                  "text"
    description            "text"
    rights                 "text"
history table:
    crop                   "angle,cx,cy,cw,ch"
                           Note: angle is the rotation angle before crop, positive clockwise,
                                 cx, cy, cw, ch are the normalized crop coordinates (0.0 to 1.0),
                                 cx,cy is lower left(?) and cw,ch are new width and height.
tags and tagged_images tables:
    tag                    "text"
                           Note: you may add tags but not modify or remove existing tags.

NOTES:
  1) before modifying the database dt will check to make sure darktable is not running
  2) if a modification is going to be made to the database a backup will be made first: <library.db>.<timestamp>
     unless you specify --no-backup

positional arguments:
  <command>           mv, query, set, etc
  <parameter>

optional arguments:
  -h, --help          show this help message and exit
  -d DTDB, --db DTDB  Darktable database path, default=
                      ~/.config/darktable/library.db
  --no-backup         don't backup the Darktable database before modifications
```

Here is an example:

```
~/Darktable/raw/test1$ dt query IMG_0004.CR2

query [/home/wayne/Darktable/raw/test1/IMG_0004.CR2]
	/home/wayne/Darktable/raw/test1/IMG_0004.CR2 is a valid file
	checking for film roll [/home/wayne/Darktable/raw/test1]
	image [IMG_0004.CR2] is id [12236] in film roll [165]
	image IMG_0004.CR2 in film roll /home/wayne/Darktable/raw/test1:
		IMG_0004.CR2[datetime_taken]             2012:09:21 20:25:52
		IMG_0004.CR2[caption]                                       
		IMG_0004.CR2[description]                                   
		IMG_0004.CR2[license]                                       
		IMG_0004.CR2[longitude]                                 None
		IMG_0004.CR2[latitude]                                  None

	history:

	tags:
		                                                        name                   description
		IMG_0004.CR2[271]                       darktable|format|cr2                          None

	meta_data:


~/Darktable/raw/test1$ dt mv IMG_0004.CR2 image-0004.cr2
success: [165][12236] renamed from [/home/wayne/Darktable/raw/test1/IMG_0004.CR2] to [/home/wayne/Darktable/raw/test1/image-0004.cr2]

~/Darktable/raw/test1$ dt set image-0004.cr2 tag "this is a test" longitude 9.974650383 latitude 50.3703308105 title "this is the title" description "this is the caption" creator "this is me" rights "or lefts?" caption "this is also a caption"
insert into meta_data values (12236, 4, "or lefts?")
insert into meta_data values (12236, 3, "this is the caption")
add description = this is the caption
insert into meta_data values (12236, 2, "this is the title")
insert into meta_data values (12236, 0, "this is me")
add longitude = 9.974650383
add caption = this is also a caption
add latitude = 50.3703308105
tag[278]="this is a test" already exists
insert into tagged_images values (12236,278)

~/Darktable/raw/test1$ dt query image-0004.cr2

query [/home/wayne/Darktable/raw/test1/image-0004.cr2]
	/home/wayne/Darktable/raw/test1/image-0004.cr2 is a valid file
	checking for film roll [/home/wayne/Darktable/raw/test1]
	image [image-0004.cr2] is id [12236] in film roll [165]
	image image-0004.cr2 in film roll /home/wayne/Darktable/raw/test1:
		image-0004.cr2[datetime_taken]           2012:09:21 20:25:52
		image-0004.cr2[caption]               this is also a caption
		image-0004.cr2[description]              this is the caption
		image-0004.cr2[license]                                     
		image-0004.cr2[longitude]                        9.974650383
		image-0004.cr2[latitude]                       50.3703308105

	history:

	tags:
		                                                        name                   description
		image-0004.cr2[271]                     darktable|format|cr2                          None
		image-0004.cr2[278]                           this is a test                          None

	meta_data:
		                                                                                     value
		image-0004.cr2[rights]                                                           or lefts?
		image-0004.cr2[description]                                            this is the caption
		image-0004.cr2[title]                                                    this is the title
		image-0004.cr2[creator]                                                         this is me

```

Now when you next run Darktable you should see all these values displayed.
