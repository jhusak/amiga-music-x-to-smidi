 Author: Jakub Husak, 13.06.2010, version 0.4.

 You may do whatever you want with this software, unless you use the idea and algorithms in commercial software.
 
 No warranty. You are on your own.

 Usage: mx2smf.py file.perf [v|vv|vvv]

 This is the converter for old-time Music-X sequencer for Commodore Amiga
 to more handy format SMF-0.

 The code is not clean; it uses some hacks, but it works well
 No cycle checking. No source file format error checking. You have been warned.

 Some commands used in Music-X are not converted (simply discarded) because I simply do not use them in Music-X Performances (you will know about it, the converter outs the UNKNOWN message with parameters.)
 If you want them, contact me through http://husak.pl

 This was a little reverse-engineering of original Music-X file, but three days of writing and testing were worth of it.
 I was lucky, because in the Music-X file the event timing was different but easy to understand.
 The rest are ordinary midi events sometimes enveloped in some constant-length structures + some meta-events not used in midi stream.

 CHANGELOG

 Fixed from 0.4: (2010-06-18)
 - Fixed sequence length setting (when sequence offset is not 0)
 - changed 'len' variables to 'length' not to be in potential conflict with func
 - added reverse sorting of events by event type before write;
   now pgmchg, ctrlchg always before note on; note on before note off. good
 
 Fixed from 0.3: (2010-06-13)
 - file format checking added
 
 Fixed from 0.2: (2010-06-10)
 - unroll sequences now works ok. (not only first unroll)
 
 Fixed from 0.1: (2010-06-08)
 - The code has a little problems with unrolling sequences, sometimes the last note is fired
 but not finished, this leads to endless notes playing. I have met this problem once or twice,
 it is easy to remove the notes manually.
 - Code cleanup

 Initial version: 0.1: (2010-06-08)


