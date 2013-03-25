#!/usr/bin/python

'''
This file is part of dt.

Dt is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Dt is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Dt.  If not, see <http://www.gnu.org/licenses/>.

Copyright 2012 Wayne Vosberg <wayne.vosberg@mindtunnel.com>

'''

'''

db schema version 36:

CREATE TABLE color_labels (imgid integer, color integer);
CREATE TABLE film_rolls (id integer primary key, datetime_accessed char(20), folder varchar(1024));
CREATE TABLE history (imgid integer, num integer, module integer, operation varchar(256), 
        op_params blob, enabled integer,blendop_params blob, blendop_version integer, 
        multi_priority integer, multi_name varchar(256));
CREATE TABLE images (id integer primary key, film_id integer, width int, height int, filename varchar,
        maker varchar, model varchar, lens varchar, exposure real, aperture real, iso real, 
        focal_length real, focus_distance real, datetime_taken char(20), flags integer, 
        output_width integer, output_height integer, crop real, raw_parameters integer, 
        raw_denoise_threshold real, raw_auto_bright_threshold real, raw_black real, raw_maximum real, 
        caption varchar, description varchar, license varchar, sha1sum char(40), orientation integer,
        group_id integer, histogram blob, lightmap blob, longitude double, latitude double, 
        color_matrix blob, colorspace integer);
CREATE TABLE legacy_presets (name varchar, description varchar, operation varchar, 
        op_version integer, op_params blob, enabled integer, blendop_params blob, 
        blendop_version integer, multi_priority integer, multi_name varchar, model varchar, 
        maker varchar, lens varchar, iso_min real, iso_max real, exposure_min real, 
        exposure_max real, aperture_min real, aperture_max real, focal_length_min real, 
        focal_length_max real, writeprotect integer, autoapply integer, filter integer, 
        def integer, isldr integer);
CREATE TABLE lock (id integer);
CREATE TABLE meta_data (id integer,key integer,value varchar);
CREATE TABLE presets (name varchar, description varchar, operation varchar, op_version integer, 
        op_params blob, enabled integer, blendop_params blob, model varchar, maker varchar, 
        lens varchar, iso_min real, iso_max real, exposure_min real, exposure_max real, 
        aperture_min real, aperture_max real, focal_length_min real, focal_length_max real, 
        writeprotect integer, autoapply integer, filter integer, def integer, isldr integer, 
        blendop_version integer, multi_priority integer, multi_name varchar(256));
CREATE TABLE selected_images (imgid integer primary key);
CREATE TABLE settings (settings blob);
CREATE TABLE style_items (styleid integer,num integer,module integer,operation varchar(256),
        op_params blob,enabled integer,blendop_params blob, blendop_version integer, 
        multi_priority integer, multi_name varchar(256));
CREATE TABLE styles (name varchar,description varchar);
CREATE TABLE tagged_images (imgid integer, tagid integer, primary key(imgid, tagid));
CREATE TABLE tags (id integer primary key, name varchar, icon blob, description varchar, flags integer);
CREATE TABLE tagxtag (id1 integer, id2 integer, count integer, primary key(id1, id2));
CREATE INDEX group_id_index on images (group_id);
CREATE INDEX imgid_index on history (imgid);

'''

import os
import sqlite3
import sys
import argparse
import textwrap
import struct
from datetime import datetime
import shutil
import subprocess
import re

dbVer = 0;

def is_running(process, owner):
    '''raise exception if user is running process'''
    
    s = subprocess.Popen(["ps", "-U", owner],stdout=subprocess.PIPE)
    for x in s.stdout:
        if re.search(process, x):
            raise Exception('user %s is currently running %s'%(owner,process))



def do_backup(dbFile,doIt):
    '''create a backup of the dbFile using the current isoformat timestamp as the extension'''
    
    if doIt:
        tStamp = datetime.now().isoformat()
        try:
            shutil.copyfile(dbFile,dbFile+'.'+tStamp)
        except:
            raise Exception('failed to create backup file [%s]'%doIt+'.'+tStamp)



def getVersion(buf):
    ''' return the first 8 bytes as the schema version number '''
    
    if type(buf) == str:
        val = buf
    else:
        val = ''
        for B in buf[0:8]:
            val += '%02x'%ord(B)
    
    s_ver = val[0:8]
    
    ver = struct.unpack('<I',s_ver.decode('hex'))[0]
    
    return ver



def unPack(buf):
    ''' unpack the crop and rotating module (clipping) op_params blob and print it.'''
    
    if type(buf) == str and len(buf) == 56:
        val = buf
    elif len(buf) == 28:
        val=''
        for B in buf:
            val+='%02x'%ord(B)
    else:
        raise ValueError('buf (len:%d)(type:%s)(str:%s) not understood!!!'%\
            (len(buf),type(buf),buf))

    s_ang = val[0:8]
    s_cx = val[8:16]
    s_cy = val[16:24]
    s_cw = val[24:32]
    s_ch = val[32:40]
    s_k_h = val[40:48]
    s_k_v = val[48:56]

    ang = struct.unpack('<f',s_ang.decode('hex'))[0]
    cx = struct.unpack('<f',s_cx.decode('hex'))[0]
    cy = struct.unpack('<f',s_cy.decode('hex'))[0]
    cw = struct.unpack('<f',s_cw.decode('hex'))[0]
    ch = struct.unpack('<f',s_ch.decode('hex'))[0]
    k_h = struct.unpack('<f',s_k_h.decode('hex'))[0]
    k_v = struct.unpack('<f',s_k_v.decode('hex'))[0]

    fmt = '                %10s%10s%10s%10s%10s%10s%10s'
    print ''
    print fmt%('angle','cx','cy','cw','ch','k_h','k_v')
    print fmt%(s_ang,s_cx,s_cy,s_cw,s_ch,s_k_h,s_k_v)
    print '                %9.4f %9.4f %9.4f %9.4f %9.4f %9.4f %9.4f'%(ang,cx,cy,cw,ch,k_h,k_v)
    print ''
    
    


def dt_mv(conn,src,dest):
    '''
        Rename an image or film roll (both filesystem and darktable database entries).
        In the case of an image file, also rename the .xmp and .meta files if they exist.
        
    '''
    
    c = conn.cursor()

    if os.path.isdir(src):
        # renaming film roll
        srcId = fr_getId(conn,src)
        os.renames(src,dest)
        #print 'dest: %s, id: %d'%(dest,srcId)
        c.execute('update film_rolls set folder = ? where id = ?',(dest,srcId,))
        conn.commit()     
               
        # check!
        if not os.path.isdir(dest):
            raise Exception('failed to rename directory!')
        
        destId = fr_getId(conn,dest)
        if srcId != destId:
            raise Exception('failed to rename film roll!!!')    
        
        print 'success: [%d] renamed from [%s] to [%s]'%(destId,src,dest)          
 
                   
    elif os.path.isfile(src):
        # renaming image
        srcRoll = os.path.dirname(src)
        srcId = fr_getId(conn,srcRoll)
        destRoll = os.path.dirname(dest)
        if srcRoll != destRoll:
            if os.path.isdir(destRoll):
                destId = fr_getId(conn,destRoll)
            else:
                raise Exception('destination folder [%s] must already exist and be imported before moving images to it!'%destRoll)
        else:
            destId = srcId
            
        (imFile,imType) = os.path.splitext(os.path.basename(src))
        if not ( imType.lower() == '.xmp' or imType.lower() == '.meta' ):
                imFile += imType
        else:
            raise Exception('Cannot rename .xmp or .meta file')
        
        imId = im_getId(conn,srcId,imFile)
        
        os.rename(src,dest)
        if os.path.isfile(src+'.xmp'):
            os.rename(src+'.xmp',dest+'.xmp')
        if os.path.isfile(src+'.meta'):
            os.rename(src+'.meta',dest+'.meta')
        c.execute('update images set film_id = ?, filename = ? where id = ?',(destId,os.path.basename(dest),imId,))
        conn.commit() 
        
        # check
        if not os.path.isfile(dest):
            raise Exception('failed to rename file!')
        
        destId = fr_getId(conn,os.path.dirname(dest))
        imId = im_getId(conn,destId,os.path.basename(dest))
        print 'success: [%d][%d] renamed from [%s] to [%s]'%(destId,imId,src,dest)
            
    else:
        raise Exception('source [%s] is not found!'%src)
    
    
    
def scan(conn,qFile):
    '''check if an image exists in the database'''
    
    if os.path.isdir(qFile):
        try:
            frId = fr_getId(conn,qFile)
        except:
            raise Exception('no such film roll [%s]'%qFile)
    elif os.path.isfile(qFile):
        imRoll = os.path.dirname(qFile)
        try:
            frId = fr_getId(conn,imRoll)
        except:
            raise Exception('no such film roll [%s]'%imRoll)
        try:
            (imFile,imType) = os.path.splitext(os.path.basename(qFile))
            if not ( imType.lower() == '.xmp' or imType.lower() == '.meta' ):
                imFile += imType 
            imId = im_getId(conn,frId,imFile)
        except:
            raise Exception('file [%s] does not exist in film roll [%s]'%(qFile,imRoll))
        


def query(conn,qFile):
    '''query image or directory'''
    
    tUnknown = 0
    tRoll = 1
    tImage = 2
    tMeta = 3
    
    print '\nquery [%s]'%qFile
    qType = tUnknown
    if os.path.isdir(qFile):
        print '  %s is a valid directory'%qFile
        qType = tRoll
        imRoll = qFile
        imFile = None
    elif os.path.isfile(qFile):
        print '  %s is a valid file'%qFile
        qType = tImage
        imRoll = os.path.dirname(qFile)
        imFile = os.path.basename(qFile)
    else:
        print '  %s is not a dir or file'%qFile
        print '    check if it is listed as a film roll:'
        try:
            frId = fr_getId(conn,qFile)
            print '    %s was a film roll but the source directory is now missing!'%qFile
        except:
            print '    no!  check if parent was a film roll:'
            try:
                frId = fr_getId(conn,os.path.dirname(qFile))
                print '    film roll %s exists but file %s does not!'%(os.path.dirname(qFile),os.path.basename(qFile))
            except:
                print '    no! [%s] was not found!'%qFile
        
    if qType == tRoll:
        try:
            frId = fr_getId(conn,imRoll)
            print '  film roll [%s] is id [%d]'%(imRoll,frId)
        except:
            print '  error: %s'%sys.exc_info()[1]
            
    if qType == tImage:
        try:
            print '  checking for film roll [%s]'%imRoll
            frId = fr_getId(conn,imRoll)
            imId = im_getId(conn,frId,imFile)
            print '  image [%s] is id [%d] in film roll [%d]'%(imFile,imId,frId)
            im_getAll(conn,frId,imFile)
            im_getHistory(conn,imId)
            im_getTags(conn,imId)
            im_getMeta(conn,imId)
        except:
            print '  error: %s'%sys.exc_info()[1]
                    


def im_setMeta(conn,imId,var,val):
    ''' set image meta_data: creator, publisher, title, description, rights
    
        meta_data (id integer,key integer,value varchar);

    '''                    
    
    keys = [ 'creator', 'publisher', 'title', 'description', 'rights' ]
    key = keys.index(var)
    
    c = conn.cursor()
    
    curVal = c.execute('select value from meta_data where id = ? and key = ?',(imId,key,)).fetchone()
    if curVal == None:
        print 'insert into meta_data values (%d, %d, "%s")'%(imId,key,val)
        c.execute('insert into meta_data values (?, ?, ?)',(imId,key,val))
    else:
        print 'update meta_data set value = "%s" where id = %d and key = %d'%(val,imId,key)
        c.execute('update meta_data set value = ? where id = ? and key = ?',(val,imId,key))
    conn.commit()
    
                   
  
def im_getMeta(conn,imId):
    ''' get image meta_data:  creator, publisher, title, description, rights
    
        meta_data (id integer,key integer,value varchar);
    
    '''
    
    header = True
    c = conn.cursor()
    imName = im_getName(conn,imId)
    keys = [ 'creator', 'publisher', 'title', 'description', 'rights' ]
    fmt = '    %-35s%60s'
    
    print '\n  meta_data:'
    for meta in c.execute('select * from meta_data where id = ?',(imId,)):
        if header:
            print fmt%('','value')
            header = False
        
        try:
            key = keys[meta['key']]
        except:
            key = '<%d unknown>'%meta['key']
   
        print fmt%(imName+'['+key+']',meta['value'])
        


def im_setTag(conn,imId,tagText):
    ''' set a tag on an image:
    
        tagged_images (imgid integer, tagid integer, primary key(imgid, tagid));
        tags (id integer primary key, name varchar, icon blob, description varchar, flags integer);
    
    '''
    
    c = conn.cursor()
    
    # make sure tag is in the tags table
    try:
        (tagId,) = c.execute('select id from tags where name = ?',(tagText,)).fetchone()
    except:
        tagId = None
        
    if tagId == None:
        print 'insert into tags values (NULL,"%s",NULL,NULL,NULL)'%tagText
        c.execute('insert into tags values (NULL,?,NULL,NULL,NULL)',(tagText,))
        conn.commit()
        (tagId, ) = c.execute('select id from tags where name = ?',(tagText,)).fetchone()
    else:
        print 'tag[%d]="%s" already exists'%(tagId,tagText)

        
    if tagId == None:
        raise Exception('failed to add [%s] to tags table'%tagText)
    
    # and then make sure it is in the tagged_images table
    hit = c.execute('select * from tagged_images where imgid = ? and tagid = ?',(imId,tagId)).fetchone()
    if hit == None:
        print 'insert into tagged_images values (%d,%d)'%(imId,tagId)
        c.execute('insert into tagged_images values (?,?)',(imId,tagId,))
        conn.commit()
    else:
        print 'image ID [%d] already references tag[%d]=%s'%(hit['imgid'],hit['tagid'],tagText)
        
        
    
def im_getTags(conn,imId):
    ''' display tags:
        tagged_images (imgid integer, tagid integer, primary key(imgid, tagid));
        tags (id integer primary key, name varchar, icon blob, description varchar, flags integer);
    
    '''
    
    header = True
    c=conn.cursor()
    imName = im_getName(conn,imId)
    fmt = '    %-30s%30s%30s'
    
    print '\n  tags:'
    
    for tagId in c.execute('select tagid from tagged_images where imgid = ?',(imId,)):
        if header:
            print fmt%('','name','description')
            header = False
            
        d=conn.cursor()
        try:            
            tagStr = d.execute('select * from tags where id = ?',(tagId[0],)).fetchone()
            print fmt%(imName+'[%d]'%tagId[0],tagStr['name'],tagStr['description'])
        except:
            print fmt%(imName+'[%d]'%tagId[0],'<None>','<None>')
            
        

def im_getHistory(conn,imId):
    '''    get image history:
    
        v.34: history (imgid integer, num integer, module integer, operation varchar(256), 
            op_params blob, enabled integer,blendop_params blob, blendop_version integer);
            
        v.36: history (imgid integer, num integer, module integer, operation varchar(256), 
            op_params blob, enabled integer,blendop_params blob, blendop_version integer, 
            multi_priority integer, multi_name varchar(256));
        
        crop and rotate entries (module = 3, operation = clipping) will be expanded
        
    '''
    global dbVer    
    header = True
    c=conn.cursor()
    imName = im_getName(conn,imId)
    #fmt34='    %-30s%10s%10s%10s%12s%14s%10s%16s%16s'
    #fmt36='    %-30s%10s%10s%10s%12s%14s%10s%16s%16s%16s%32s'
    
    print '\n  history:'  
    for HI in c.execute('select * from history where imgId = ?',(imId,)):
        if header:
            #print '\t\t   ',
            print '    %-25s'%' ',
            for h in HI.keys():
                print '%*s'%(len(h)+4,h),
            print '\n'
            
            '''
            if dbVer == 34:
                print fmt34%('',HI.keys()[0],HI.keys()[1],HI.keys()[2],HI.keys()[3],\
                           HI.keys()[4],HI.keys()[5],HI.keys()[6],HI.keys()[7])
            elif dbVer == 36:
                print fmt36%('',HI.keys()[0],HI.keys()[1],HI.keys()[2],HI.keys()[3],\
                           HI.keys()[4],HI.keys()[5],HI.keys()[6],HI.keys()[7],HI.keys()[8], \
                           HI.keys()[9])
            '''
            header = False
        
        print '    %-25s'%(imName+'['+str(HI['num'])+']'),
        i=0
        for v in HI:
            if type(v) == buffer:
                print '%*s'%(len(HI.keys()[i])+4,'<blob>'),
            else:
                print '%*s'%(len(HI.keys()[i])+4,v),
            i+=1
        print '\n'
           
        #print fmt34%(imName+'['+str(HI['num'])+']',HI[0],HI[1],HI[2],HI[3],'<blob>',HI[5],'<blob>', \
        #    HI[7])
        
        # if this is a crop & rotate module, dump the details
        if HI['operation'] == 'clipping':
            unPack(HI['op_params'])
        
        

def im_setHistory(conn,imId,val):
    '''    set image history: (currently only adds a crop & rotate entry)
    
        v.34: history (imgid integer, num integer, module integer, operation varchar(256), 
            op_params blob, enabled integer,blendop_params blob, blendop_version integer);
            
        v.36: history (imgid integer, num integer, module integer, operation varchar(256), 
            op_params blob, enabled integer,blendop_params blob, blendop_version integer, 
            multi_priority integer, multi_name varchar(256));
                
    '''
    global dbVer
    
    c = conn.cursor()
    
    (nAng,nCx,nCy,nCw,nCh) = eval(val)
    newOpXmp = struct.pack('<fffffff',nAng,nCx,nCy,nCw,nCh,0.0,0.0)
    newBopXmp = struct.pack('<fff',0,0,0)
    
    n = c.execute('select num from history where imgid = ?',(imId,)).fetchall()
    entry = len(n)
    # just retain any previous blendop_params and blendop_version
    blendop = None
    try:
        (blendop,blendop_ver) = c.execute(
            'select blendop_params, blendop_version from history where imgid = ?',(imId,)).fetchone()
    except:
        pass
    
    if blendop == None:
        blendop = sqlite3.Binary(newBopXmp)
        blendop_ver = 1
    if dbVer == 34:
        c.execute('insert into history values(?,?,?,?,?,?,?,?)',(imId,entry,3,'clipping',sqlite3.Binary(newOpXmp),1,blendop,blendop_ver))
    elif dbVer == 36:
        multi_priority = 0
        multi_name = ''
        try:
            (multi_priority,multi_name) = c.execute('select multi_priority, multi_name from history where imgid = ?',(imId,)).fetchone()           
        except:
            pass
        c.execute('insert into history values(?,?,?,?,?,?,?,?,?,?)',(imId,entry,3,'clipping',sqlite3.Binary(newOpXmp),1,blendop,blendop_ver,multi_priority,multi_name))
    
    
    #c.execute('insert into history values(?,?,?,?,?,?,?,?)',(imId,entry,3,'clipping',sqlite3.Binary(newOpXmp),1,sqlite3.Binary(newBopXmp)),blendop_ver)
    
    conn.commit()

    
    
def im_getId(conn,frId, name):
    '''    return the image id
        images (id integer primary key, film_id integer, width int, height int, 
        filename varchar, maker varchar, model varchar, lens varchar, 
        exposure real, aperture real, iso real, focal_length real, 
        focus_distance real, datetime_taken char(20), flags integer, 
        output_width integer, output_height integer, crop real, 
        raw_parameters integer, raw_denoise_threshold real, 
        raw_auto_bright_threshold real, raw_black real, raw_maximum real, 
        caption varchar, description varchar, license varchar, 
        sha1sum char(40), orientation integer, group_id integer, 
        histogram blob, lightmap blob, longitude double, latitude double, 
        color_matrix blob);
    
    '''
    
    c=conn.cursor()
    ids = c.execute('select id from images where film_id = ? and filename = ?',(frId,name,)).\
        fetchall()
    
    if len(ids) == 1:
        return ids[0][0]
    else:
        raise Exception('failed to find image [%s] in film roll [%d]'%(name,frId))



def im_getName(conn,imId):
    '''return the image name'''
    
    c=conn.cursor()
    ids = c.execute('select filename from images where id = ?',(imId,)).fetchall()
    if len(ids) == 1:
        return ids[0][0]
    else:
        raise Exception('failed to find image with id [%d]'%imId)



def im_setImage(conn,imId,key,val):
    '''    set some image table values: datetime_taken, caption, description, license, longitude, latitude
    
        images (id integer primary key, film_id integer, width int, height int, 
        filename varchar, maker varchar, model varchar, lens varchar, 
        exposure real, aperture real, iso real, focal_length real, 
        focus_distance real, datetime_taken char(20), flags integer, 
        output_width integer, output_height integer, crop real, 
        raw_parameters integer, raw_denoise_threshold real, 
        raw_auto_bright_threshold real, raw_black real, raw_maximum real, 
        caption varchar, description varchar, license varchar, 
        sha1sum char(40), orientation integer, group_id integer, 
        histogram blob, lightmap blob, longitude double, latitude double, 
        color_matrix blob);
    
    '''
        
    c = conn.cursor()
    keys = [ 'datetime_taken', 'caption', 'description', 'license', 'longitude', 'latitude' ]
       
    if key in keys:
        sQl='select %s from images where id = ?'%key
        (curVal,) = c.execute(sQl,(imId,)).fetchone()
        if curVal == None or curVal == '':
            print 'add %s = %s'%(key,val)
        else:
            print 'replace %s = %s with %s'%(key,curVal,val)
            
        sQl='update images set %s = ? where id = ?'%key
        c.execute(sQl,(val,imId))
        conn.commit()
    else:
        raise Exception('image table key [%s] not known'%key)
    
    
    
def im_getAll(conn,frId,name):
    '''print the values I hope to be able to change'''
    
    c=conn.cursor()
    fmt = '    %-35s%-30s'
    keys = [ 'datetime_taken', 'caption', 'description', 'license', 'longitude', 'latitude' ]
    
    imRow = c.execute('select datetime_taken, caption, description, license, longitude, latitude from images where film_id = ? and filename = ?',(frId,name,)).fetchone()  
    print '  image %s in film roll %s:'%(name,fr_getName(conn,frId))
    for k in keys:
        print fmt%(name+'['+k+']',imRow[k])    
 
    

def fr_getName(conn,frId):
    '''return the film roll name'''
    
    c=conn.cursor()
    ids = c.execute('select folder from film_rolls where id = ?',(frId,)).\
        fetchall()
        
    if len(ids) == 1:
        return ids[0][0]
    else:
        raise Exception('failed to find film roll id [%d]'%frId)
    
    
        
def fr_getId(conn, name):
    '''return the film roll index
        film_rolls (id integer primary key, datetime_accessed char(20), 
            folder varchar(1024));
        
        where datetime_accessed = "YYYY:MM:DD HH:MM:SS"
        and folder is FQPN
        
    '''
  
    c=conn.cursor()
    ids = c.execute('select id from film_rolls where folder = ?',(name,)).\
        fetchall()
        
    if len(ids) == 1:
        return ids[0][0]
    else:
        raise Exception('failed to find film roll [%s]'%name)
    
    
    
def dt():
    '''darktable sqlite3 database maintenance'''
    
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent(
            '''
            Darktable filmroll/image/metadata maintenance:
            
            mv <src> <dest>                             : rename film roll or image
            query <dir|file> [ <dir|file> ... ]         : dump details of an object
                                                          (best on 132+ column term)
            scan <dir|file> [ <dir}|file> ... ]         : just report if the object 
                                                          doesn't exist in the db - 
                                                          .xmp and .meta extensions 
                                                          will be stripped before the 
                                                          check
            set <image> <var> <val> [ <var> <val> ... ] : modify metadata (Note 6)
            
            For the 'set' command, the valid var's are:
            
            image table:
                datetime_taken         "YYYY:MM:DD HH:MM:SS"
                caption                "text"
                description            "text"
                license                "text"
                longitude              float (-180.0 to +180.0, positive E) (Note 3)
                latitude               float (-90.0 to +90.0, positive N) (Note 3)
                                       
            meta_data table:
                creator                "text"
                publisher              "text"
                title                  "text"
                description            "text"
                rights                 "text"
            history table:
                crop                   "angle,cx,cy,cw,ch" (Note 4)
                                       
            tags and tagged_images tables:
                tag                    "text" (Note 5)
                                       
            NOTES:
              1) before modifying the database dt will check to make sure darktable 
                 is not running
              2) if a modification is going to be made to the database a backup will 
                 be made first: <library.db>.<timestamp>, unless you specify --no-backup
              3) to convert degrees minutes seconds to a float: 
                    f = degrees + ( minutes + seconds/60. ) / 60.
                 and change sign if W or S.
              4) angle is the rotation angle before crop, positive clockwise,
                 cx, cy, cw, ch are the normalized crop coordinates (0.0 to 1.0),
                 cx,cy is lower left(?) and cw,ch are new width and height.
              5) you may add tags but not modify or remove existing tags
              6) if any of the variables you want to use in the set command begin with
                 a "-", add a "--" option before the file name so that the python 
                 argparser doesn't try to interpret them 
                 (i.e. set -- file.jpg crop -1,0,0,1,1)
            
            '''))
    
    global dbVer
    
    parser.add_argument('-d', '--db', dest='dtdb', action='store',
        default=os.getenv("HOME")+os.sep+'.config'+os.sep+'darktable'+os.sep+'library.db',
        help='Darktable database path, default= ~/.config/darktable/library.db')
    
    parser.add_argument('--no-backup', dest='doBackup', default=True, action='store_false',
        help='don\'t backup the Darktable database before modifications')
    
    parser.add_argument('cmd', metavar='<command>', type=str,
        help='mv, query, set, etc')

    parser.parse_args(['--', '-f'])
    
    parser.add_argument('files', metavar='<parm>', type=str, nargs='+')
    
    args = parser.parse_args()
    
    # connect to the darktable library.db file
    
    try:
        if os.path.exists(args.dtdb):
            conn = sqlite3.connect(args.dtdb)
        else:
            raise Exception('%s does not exist'%args.dtdb)
        
        
        conn.row_factory = sqlite3.Row
        conn.text_factory = str
        c = conn.cursor()
        '''
            Here is the darktable settings blob:
            
            typedef struct dt_ctl_settings_t
                {
                  // TODO: remove most of these options, maybe the whole struct?
                  // global
                  int32_t version;
                  char dbname[512];
                
                  int32_t lib_image_mouse_over_id;
                
                  // synchronized navigation
                  float dev_zoom_x, dev_zoom_y, dev_zoom_scale;
                  dt_dev_zoom_t dev_zoom;
                  int dev_closeup;
                }
                dt_ctl_settings_t;
        '''
        try:
            vblob = c.execute('select settings from settings').fetchone()[0]
            dbVer = getVersion(vblob)
            if dbVer != 34 and dbVer != 36:
                raise Exception('%s '%args.dtdb + 'version %d is not 34 or 36!'%dbVer)
            
        except:
            #print 'error: ',sys.exc_info()
            raise Exception('%s '%args.dtdb + 'does not appear to be a Darktable database')

    except:
        print 'darktable db error: %s '%sys.exc_info()[1]
        sys.exit()
    
    
    
    if args.cmd == 'query':
        for qFile in args.files:
            try:
                query(conn,os.path.abspath(qFile))
            except:
                print 'error: [%s]'%sys.exc_info()[1]
                
    elif args.cmd == 'scan':
        for qFile in args.files:
            try:
                scan(conn,os.path.abspath(qFile))
            except:
                print sys.exc_info()[1]
                
    elif args.cmd == 'mv':
        try:
            if len(args.files) != 2:
                raise Exception('mv <from> <to>')
            else:
                mvSrc  = os.path.abspath(args.files[0])
                mvDest = os.path.abspath(args.files[1])             
                
            is_running('darktable',os.getenv('USER'))
            do_backup(args.dtdb,args.doBackup)
            dt_mv(conn,mvSrc,mvDest)
        except:
            print 'error: %s'%sys.exc_info()[1]
            sys.exit()
                
    elif args.cmd == 'set':
        try:
            if len(args.files) < 3:
                raise Exception('set <image> <variable> <value> ...')
            else:
                imRoll = os.path.dirname(os.path.abspath(args.files[0]))
                imName = os.path.basename(os.path.abspath(args.files[0]))
                frId = fr_getId(conn,imRoll)
                imId = im_getId(conn,frId,imName)
                # need to make each tag key unique so I can create a dict using it as key
                for i in range(1,len(args.files),2):
                    if args.files[i] == 'tag':
                        args.files[i] = 'tag---%d'%i 
       
                imVars = dict(zip(args.files[1::2], args.files[2::2]))
                # check that # of keys = # of values
                if len(imVars)*2 != len(args.files)-1:
                    raise Exception('Failed to convert %s to dict.  Missing value?'%args.files[1:])
            
            is_running('darktable',os.getenv('USER'))
            do_backup(args.dtdb,args.doBackup)
            
            metaKeys = [ 'creator', 'publisher', 'title', 'description', 'rights' ]
            imageKeys = [ 'datetime_taken', 'caption', 'description', 'license', 'longitude', 'latitude' ]
            historyKeys = [ 'crop' ]
            #print 'imVars: ',imVars
            for k,v in imVars.iteritems():
                if k in metaKeys:
                    im_setMeta(conn,imId,k,v)
                if k in imageKeys:
                    im_setImage(conn,imId,k,v)
                if k in historyKeys: # there is only one valid right now ....
                    im_setHistory(conn,imId,v)
                if k.startswith('tag---'):
                    im_setTag(conn,imId,v)
            
        except:
            print 'error: ',sys.exc_info()
            sys.exit()           
    else:
        print 'command??'          
            

    
if __name__ == '__main__':
    dt()
