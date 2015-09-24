#!/usr/bin/python
# change the line above to reflect your python place
#
# Author: Jakub Husak, 13.06.2010, version 0.4
# You may do whatever you want with this softy, unless you use the idea and algos in commercial software.
# 
# No warranty. You are on your own.
#
# This is Converter for old-time Music-X sequencer for Commodore Amiga
# to more handy format SMF-0
# The code is not clean. It uses some hacks, but it works well
# No cycle checking. No source file format error checking. You have been warned.
# Some commands used in Music-X are not converted (simply discarded)
# because I simply do not use them in M-X Performances
# If you want them, contact me through http://husak.com.pl
# (You will know about it, the converter outs the UNKNOWN message with parameters.)
#
# This was a little reverse-engineering of original Music-X file, but three days of
# writing and testing were worth of it.
# I'am lucky, because in the MX file the event timing was different but easy to understand.
# The rest are ordinary midi events sometimes enveloped in some constant-length structures +
# some meta-events not used in midi stream.
#
# CHANGELOG
#
# Fixed from 0.4: (2010-06-18)
# - Fixed sequence length setting (when sequence offset is not 0)
# - changed 'len' variables to 'length' not to be in potential conflict with func
# - added reverse sorting of events by event type before write;
#   now pgmchg, ctrlchg always before note on; note on before note off. good
# 
# Fixed from 0.3: (2010-06-13)
# - file format checking added
# 
# Fixed from 0.2: (2010-06-10)
# - unroll sequences now works ok. (not only first unroll)
# 
# Fixed from 0.1: (2010-06-08)
# - The code has a little problems with unrolling sequences, sometimes the last note is fired
# but not finished, this leads to endless notes playing. I have met this problem once or twice,
# it is easy to remove the notes manually.
# - Code cleanup
#
# Initial version: 0.1: (2010-06-08)
#
# Usage: mx2smf.py file.perf [v|vv|vvv]
#
from chunk import *
import sys
import os
import string
from traceback import print_exc
from struct import pack
from types import StringType
from cStringIO import StringIO

class MusicX2Midi0:

	def __init__(self):
		self.__sequences={}
		self.__templsequences={}
		self.__merged_sequence={}
		# for 4/4
		self.__metrummult=0x300
		self.__tempo=120

	def setSequence(self,seqnum,seq,is_on,length,rep):
		self.__sequences[seqnum]=(is_on,length,seq,rep)

	def setTemplateSequence(self,seqnum,seq,is_on,length,rep):
		self.__templsequences[seqnum]=(is_on,length,seq,rep)

	def unrollSeq(self,mark,seq,transp,endmark):
		""" Builds event list for single sequence (unrolled)
		"""

		resdict={}

		if transp>63:
			transp = -128+transp
		turn=0
		leave=False
		while True:

			for i in sorted(self.__templsequences[seq][2]):

				if (i[0]+turn>=endmark-mark):
					leave=True
					break
				se=self.__templsequences[seq][2][i]
				if se[0] & 0xf0 == 0x90 or se[0] in (0x70,72):

					l=list(se)
					if se[0] & 0xf90 == 0x90:
						l[1]+=transp
					l[3]+=turn+mark
					se=tuple(l)


				ind=(i[0]+turn+mark,len(resdict))
				resdict[ind]=se

			if leave: break

			turn+=self.__templsequences[seq][1]

		return resdict

	def unrollSequences(self):
		""" Replaces "Play sequence" events with hard events (sequence body) unrolled.
		"""
		seqs=self.__sequences
		slist=sorted(seqs)
		outseq={}
		endpos=0
		
		while True:
			processed=False
			for seq in slist:
				# if not one of main seqs
				if not seqs[seq][0]:
					continue

				seqitems=seqs[seq][2].items()
				# filter out 
				rollevents=dict(filter(lambda x: x[1][0]==0x70,seqitems))
				
				if not rollevents: continue;

				processed=True

				seqevents=dict(filter(lambda x: x[1][0]!=0x70,seqitems))

				for evkey in rollevents:

					re=rollevents[evkey]
					unrolledevents=self.unrollSeq(evkey[0],re[1],re[2],re[3])

					for u in unrolledevents:
						seqevents[(u[0],seq,len(seqevents))]=unrolledevents[u]
				
				te=list(seqs[seq])
				te[2]=seqevents
				self.__sequences[seq] = tuple(te)

			if not processed: break;

		return

	def mergeSequences(self):
		""" Merges all sequences into one stream, handling repeat command.
		"""
		seqs=self.__sequences
		slist=sorted(seqs)
		outseq={}
		endpos=0
		for seq in slist:

			if not seqs[seq][0]: continue

			if endpos<seqs[seq][1]: endpos=seqs[seq][1]

			turn=0
			# handling repeat command; when not used == 1
			for repeat in range(seqs[seq][3]):
				ts={}

				for t in sorted(seqs[seq][2]):
					s=list(seqs[seq][2][t])
					if len(s)>=4: s[3]+=turn
					ts[(t[0]+turn,t[1],len(ts))]=tuple(s)

				outseq.update(ts)
				turn+=seqs[seq][1]
					
		# far far away
		outseq[(endpos,0,100000000)]=(0xff,0x2f,0x00)

		self.__merged_sequence=outseq

	def expandEvents(self):
		""" Converts Music-X midi events to real midi events. Expands notes and tempo.
		"""
		sortedseq=sorted(self.__merged_sequence)

		for i in sortedseq:
			se=self.__merged_sequence[i]
			# note command
			if se[0] & 0xf0 in (0x90,0xa0,0xb0,0xe0):
				# add note off
				if se[0] & 0xf0 == 0x90:
					i2=(se[3],0,len(self.__merged_sequence))
					self.__merged_sequence[i2]=(se[0]&0x8f,se[1],se[4])
				# update control event
				self.__merged_sequence[i]=(se[0],se[1],se[2])
			if se[0] & 0xf0 in (0xc0, 0xd0):
				self.__merged_sequence[i]=(se[0],se[1])
			# tempo command
			elif se[0] == 0x72:
				
				oldtempo=self.__tempo
				newtempo=se[1]+se[2]*128
				mark=i[0]
				marke=se[3]

				del(self.__merged_sequence[i])
				# spread the tempo change like Music-X does
				if abs(newtempo-oldtempo)>3: 
					step=abs(newtempo-oldtempo)/4
					step=min(step,(marke-mark)/24)
					for r in range(step):
						fr=float(r)/float(step)

						t=fr*float(newtempo)+(1.0-fr)*float(oldtempo)
						m=fr*float(marke)+(1.0-fr)*float(mark)

						ev = self.processTempo(int(t)%128,int(t)/128)
						self.__merged_sequence[int(m),i[1],len(self.__merged_sequence)]=ev
					t=newtempo
					ev = self.processTempo(t%128,t/128)
					self.__merged_sequence[marke,i[1],len(self.__merged_sequence)]=ev
				else:
					ev = self.processTempo(se[1],se[2])
					self.__merged_sequence[mark,i[1],len(self.__merged_sequence)]=ev
			#update metrum event
			elif (se[0] == 0x05):
				self.__merged_sequence[i] = self.processMetrum(se[1],se[2])


	def outBinary(self,fout):
		""" Writes gathered binary midi events to fout
		"""
		oldseq=0
		# sorting by event code descending.
		sortedseq = sorted(self.__merged_sequence)
		sortedseq = sorted(sortedseq,
			key = lambda t: (t[0],t[1],-(self.__merged_sequence[t][0])&0xf0))

		for seq in sortedseq:
			# print seq,self.__merged_sequence[seq]
			fout.writeVarLen(seq[0]-oldseq)
			fout.writeSlice(fromBytes(self.__merged_sequence[seq]))
			oldseq=seq[0]

	def processTempo(self,v1,v2):
		tempo =  v2*128+v1
		self.__tempo=tempo
		tval=60000000/tempo
		# print "TEMPO: ",tempo,tval,v1,v2
		v1=tval/65536
		v2=(tval/256)%256
		v3=tval%256
		return (0xff,0x51,0x03,v1,v2,v3)

	def processMetrum(self,v1,v2):
		self.__metrummult = 0x300*v1/(2**v2)
		return (0xff,0x58,0x04,v1%256,v2%256,0x18,0x08)

	def markconv(self,mark):
		m1=mark%0x1000
		m2=mark/0x1000
		return m2 * self.__metrummult + m1

	def AUTH(self,i=-4,typ='\x02'):
		length=chunk.getsize()
		author =chunk.read(length)
		#hack, insert fake sequence with negative number
		lenbytes=writeVar(length)
		l=['\xff', typ]
		l.extend(list(lenbytes))
		l.extend(list(author))
		s={}
		s[(0,i,0)]=tuple((ord(i) for i in l))
		self.setSequence(i,s,1,0,1)

	def NAME(self):
		self.AUTH(-3,'\x01')

	def SEQU(self):
		seqlen=chunk.getsize()
		trash=getw()
		seqnum=getw()
		seqname=chunk.read(28)
		#print "#Sequence: %s" % getstr(seqname)
		#print "#Length: %04x" % seqlen
		trash=getw();
		seqon=getw();
		trash=getw();
		seqoffset=getw();
		#print seqnum, seqon, seqoffset
		if seqon:
			seqoffset=self.markconv(seqoffset*0x1000)
		else:
			seqoffset=0
		#print "#SeqNum: %04x" % seqnum
		#print "#ON: %04x" % seqon
		#print "#Offset: %04x" % seqoffset
		#print "%08x %08x" % (getl(),getl())
		
		s={}
		seqlen=0
		seqrepeat=1
		while True:
			try:
				ev=()
				mark=self.markconv(get24())
				what=getc()
				v1=getc()
				v2=getc()
				marke=self.markconv(get24())
				v3=getc()
				#print "MARK: %08x" % mark
				#print "WHAT: %02x" % what
				
				# if ordinary midi event
				# or 0x70 - play sequence (music-x custom event)
				# or 0x72 - tempo change (spreaded in time) (music-x custom event)
				# or 0x04 - metrum change (music-x custom event)
				# copy it
				if what & 0x80 == 0x80 or what in (0x70, 0x72, 0x05):
					ev=(what,v1,v2,marke+seqoffset,v3)
				#repeat
				elif what == 0x04: seqrepeat = v1
				#end bar
				elif what == 0x00: seqlen = mark+seqoffset;
				else:
					print "$%06x: UNKNOWN %02x %02x %02x %06x %02x" % (mark,what,v1,v2,marke,v3)
				if (ev):
					s[(mark+seqoffset,seqnum,len(s))]=ev
			except EOFError:
				break;


		if (seqlen==0):
			seqlen=mark
		self.setTemplateSequence(seqnum,s,seqon,seqlen,seqrepeat)
		self.setSequence(seqnum,s,seqon,seqlen,seqrepeat)
		chunk.skip()

	def TMPO(self):
		v2=getc()
		v1=getc()
		chunk.skip()
		s={}
		#hack, insert fake sequence
		s[(0,-1,0)]=self.processTempo(v1,v2)
		self.setSequence(-1,s,1,0,1)

	def TSIG(self):
		numerator = getw()
		denominator = getw()
		chunk.skip()
		s={}
		#hack, insert fake sequence
		s[(0,0,0)]=self.processMetrum(numerator,denominator)
		self.setSequence(-2,s,1,0,1)

class RawOutstreamFile:
    def __init__(self, outfile=''):
        self.buffer = StringIO()
        self.outfile = outfile
    def writeSlice(self, str_slice):
        self.buffer.write(str_slice)
    def writeBew(self, value, length=1):
        self.writeSlice(writeBew(value, length))
    def writeVarLen(self, value):
        var = self.writeSlice(writeVar(value))
    def write(self):
        if self.outfile:
            if isinstance(self.outfile, StringType):
                outfile = open(self.outfile, 'wb')
                outfile.write(self.getvalue())
                outfile.close()
            else:
                self.outfile.write(self.getvalue())
    def close(self):
        if self.outfile:
            if not isinstance(self.outfile, StringType):
                self.outfile.close()
    def getvalue(self):
        return self.buffer.getvalue()
    def getSize(self):
        return len(self.buffer.getvalue())

def flat(*a):
	return a

def outhex():
	length=chunk.getsize()
	print ','.join([ '%02x' for i in range(length) ]) % tuple(map(lambda x: ord(x),chunk.read(length)))

def getc():
	try:
		t=chunk.read(1)
		if (t==""):
			raise EOFError
		return ord(t)
	except EOFError:
		raise	

def getw():
	return getc()*256 + getc()

def get24():
	return getw()*256 + getc()
	
def getl():
	return getw()*256*256 + getw()

def getstr(str):
	return str[0:str.find('\0')]
	
def varLen(value):
	if value <= 127:
		return 1
	elif value <= 16383:
		return 2
	elif value <= 2097151:
		return 3
	else:
		return 4

def writeVar(value):
	sevens = to_n_bits(value, varLen(value))
	for i in range(len(sevens)-1):
		sevens[i] = sevens[i] | 0x80
	return fromBytes(sevens)

def to_n_bits(value, length=1, nbits=7):
	bytes = [(value >> (i*nbits)) & 0x7F for i in range(length)]
	bytes.reverse()
	return bytes

def fromBytes(value):
	if not value:
		return ''
	return pack('%sB' % len(value), *value)

def writeBew(value, length):
	return pack('>%s' % {1:'B', 2:'H', 4:'L'}[length], value)

fnamein=sys.argv[1]
verbose=False
try:
	verbose= sys.argv[2]=="verbose"
except:
	pass

(fnameout,ext)=os.path.splitext(sys.argv[1])
fnameout+='.mid'

fhead=RawOutstreamFile(fnameout)
fbody=RawOutstreamFile('')
try:
	f=file(fnamein)

	chunk = Chunk(f)

	if chunk.getname()!="FORM": raise TypeError("FORM expected, "+chunk.getname()+" found.")
	
	type = chunk.read(4)
	if type!="MSCX": raise TypeError("MSCX expected, "+chunk.getname()+" found.")

	convert=MusicX2Midi0()

	while True:
		try:
			chunk = Chunk(f)
		except EOFError:
			break

		chunktype = chunk.getname()
		nbytes = chunk.getsize()

		try:
			method=getattr(MusicX2Midi0,chunktype)
			method(convert)
		except AttributeError:
			pass

	convert.unrollSequences()
	convert.mergeSequences()
	convert.expandEvents()
	convert.outBinary(fbody)
	size=fbody.getSize()

	# Write-out midi-0 file
	# MThd Header
	# 4d546864 00 00 00 06 00  00 00 01 00 c0
	fhead.writeSlice("MThd")
	fhead.writeSlice(fromBytes((0,0,0,0x6,0,0,0,0x1,0,0xc0)))
	# MTrk Header
	# 4d54726b 
	fhead.writeSlice("MTrk")
	fhead.writeBew(size,4)

	fhead.writeSlice(fbody.getvalue())

	fhead.write()
	fhead.close()

except IndexError:
	print "Usage: mx2smf.py file.perf"
	exit(1)

except Exception, e:
	print_exc()
	exit(1)
