SOURCE_FILE = r'Vidéo_Source.mkv'
DimensionCropBox = [1344,150] # Taille en largeur et hauteur de la CropBox délimitant les sous-titres à OCR.
HauteurCropBox = 46 # Hauteur de la CropBox délimitant les sous-titres à OCR.
HauteurCropBoxAlt = -1 # Hauteur de la CropBox Alternative, utile pour l'OCR des indications. Double le temps de traitement. Mettre à -1 pour désactiver.
# 'sinc' (2 taps, plus rapide)
# 'znedi3' (plus lent)
# 'waifu2x' (beaucoup plus lent)
UPSCALE_MODE = 'sinc' # contrôle la méthode d'Upscale
SeuilI = 230 # Seuil délimitant les sous-titres. Cette valeur correspond à la luminosité minimale de l'intérieur (Inline).
SeuilO = 80 # Seuil délimitant les sous-titres. Cette valeur correspond à la luminosité maximale de l'extérieur (Outline).
SeuilSCD = 0.03 # Un seuil trop bas augmente le nombre de faux positifs, un seuil trop haut ne permet pas de détecter tous les sous-titres.

Supersampling = -1 # Facteur de supersampling (multiplication de la résolution de la vidéo). Mettre à -1 pour calculer le facteur automatiquement.
ExpandRatio = 1 # EXPERIMENTAL ! Facteur Expand/Inpand. La valeur 1 est adaptée pour un Supersampling automatique (1080p). Calcul typique de la valeur : ExpandRatio="RésolutionFinale"/1080.

import vapoursynth as vs
import vsmasktools
import functools
import os

if UPSCALE_MODE == 'znedi3':
	import edi_rpow2 as edi

core = vs.core

def Minimum(x, y):
	return min(x, y)

Clip = core.ffms2.Source(source=SOURCE_FILE)

if type(SeuilI) is int and type(SeuilO) is int:
	Clip = core.std.ShufflePlanes(clips=Clip, planes=0, colorfamily=vs.GRAY)

if Supersampling < 0:
	if (Clip.width/Clip.height) > (16/9):	
		TargetRes = 1920
		CurrentRes = Clip.width	
	else:
		TargetRes = 1080
		CurrentRes = Clip.height
	if UPSCALE_MODE == 'znedi3':
		Ss = TargetRes/CurrentRes/1.125	
	else:
		Ss = TargetRes/CurrentRes
elif Supersampling == 0:
	Ss = 1
else:
	Ss = Supersampling

if UPSCALE_MODE == 'znedi3' and Ss != 1:

	if Ss-int(Ss) > 0:
		Ss = int(Ss/2)*2+2
	else:
		Ss = int(Ss/2)*2

	if Supersampling<0:
		Ssbis = TargetRes/(CurrentRes*Ss)
	else:
		Ssbis = Supersampling/Ss

def Resizing(clip, largeur, hauteur, hauteur2):
	clip = core.std.CropAbs(clip=clip, width=largeur, height=hauteur, left=int((clip.width-largeur)/2), top=clip.height-hauteur2)

	if Ss != 1:
		if UPSCALE_MODE == 'znedi3':
			clip = edi.znedi3_rpow2(clip=clip, rfactor=Ss)
		elif UPSCALE_MODE == 'waifu2x':
			clip = core.fmtc.bitdepth(clip=clip, bits=32)
			clip = core.w2xc.Waifu2x(clip=clip, scale=Ss)

			bits = 16 if (Ssbis != 1) else 8
			clip = core.fmtc.bitdepth(clip=clip, bits=bits)

			if Ssbis != 1:
				clip = core.fmtc.resample(clip=clip, scale=Ssbis, kernel="sinc", taps=2)
				clip = core.fmtc.bitdepth(clip=clip,bits=8)
		else:
			clip = core.fmtc.resample(clip=clip, scale=Ss, kernel="sinc", taps=2)
			clip = core.fmtc.bitdepth(clip=clip, bits=8)
	elif clip.format.bits_per_sample != 8:
		clip = core.fmtc.bitdepth(clip=clip, bits=8)
	return clip

def RGBBinarize(clip, seuil):
	R = core.std.ShufflePlanes(clips=clip, planes=0, colorfamily=vs.GRAY)
	G = core.std.ShufflePlanes(clips=clip, planes=1, colorfamily=vs.GRAY)
	B = core.std.ShufflePlanes(clips=clip, planes=2, colorfamily=vs.GRAY)
	for i in range(0, int(len(seuil)/3)):
		i = i*3
		RGB = core.std.Expr(clips=[R,G,B], 
			expr=["x " + str(seuil[i]) + " >= y " + str(seuil[i+1])+ " >= or z " + str(seuil[i+2]) + " >= or 255 0 ?"])
		if i==0:
			clipfin = RGB
		else:
			clipfin = core.std.Merge(clipfin, RGB)
	clipfin = core.std.Binarize(clip=clipfin, threshold=1)
	return clipfin

def Cleaning(clip, e):
	if type(SeuilI) is list or type(SeuilO) is list:
		clipRGB = core.fmtc.resample(clip=clip, css="444")
		clipRGB = core.fmtc.matrix(clip=clipRGB, mat="709", col_fam=vs.RGB)
		clipRGB = core.fmtc.bitdepth(clip=clipRGB, bits=8)

	if type(SeuilI) is int and type(SeuilO) is int:
		White_Raw = core.std.Binarize(clip=clip, threshold=SeuilI)
		Bright_Raw = core.std.Binarize(clip=clip, threshold=SeuilO)
	elif type(SeuilI) is int and type(SeuilO) is list:
		White_Raw = core.std.ShufflePlanes(clips=clip, planes=0, colorfamily=vs.GRAY)
		White_Raw = core.std.Binarize(clip=White_Raw, threshold=SeuilI)
		Bright_Raw = RGBBinarize(clipRGB, SeuilO)
	elif type(SeuilI) is list and type(SeuilO) is int:
		White_Raw = RGBBinarize(clipRGB, SeuilI)
		Bright_Raw = core.std.ShufflePlanes(clips=clip, planes=0, colorfamily=vs.GRAY)
		Bright_Raw = core.std.Binarize(clip=Bright_Raw, threshold=SeuilO)
	else:
		White_Raw = RGBBinarize(clipRGB, SeuilI)
		Bright_Raw = RGBBinarize(clipRGB, SeuilO)

	Bright_Out = core.std.Lut2(clipa=Bright_Raw, clipb=Rect, function=Minimum)

	Bright_Not = core.misc.Hysteresis(clipa=Bright_Out, clipb=Bright_Raw)
	Bright_Not = core.std.Invert(Bright_Not)

	White_Txt = core.std.MaskedMerge(Blank, White_Raw, Bright_Not)

	White_Lb = vsmasktools.Morpho.inpand(clip=White_Txt, sw=int(e), sh=int(e), mode=vsmasktools.types.XxpandMode.ELLIPSE)
	White_Lb = vsmasktools.Morpho.expand(clip=White_Lb, sw=int(e), sh=int(e), mode=vsmasktools.types.XxpandMode.ELLIPSE)

	White_Ub = vsmasktools.Morpho.inpand(clip=White_Txt, sw=int(5*e), sh=int(5*e), mode=vsmasktools.types.XxpandMode.ELLIPSE)
	White_Ub = vsmasktools.Morpho.expand(clip=White_Ub, sw=int(3*e), sh=int(3*e), mode=vsmasktools.types.XxpandMode.ELLIPSE)
	White_Ub = core.std.Invert(White_Ub)

	White = core.std.MaskedMerge(Blank, White_Lb, White_Ub)
	White = core.misc.Hysteresis(clipa=White, clipb=White_Txt)

	ClipCleaning = core.std.MaskedMerge(Blank, White_Raw, White)
	ClipCleaning = core.std.Median(clip=ClipCleaning)

	return ClipCleaning

def SceneLog(n, f, clip, log):
	if f.props._SceneChangeNext == 1 or f.props._SceneChangePrev == 1:
		sl_file = open(log, "a")
		sl_file.write(str(n)+" "+str(f.props._SceneChangePrev)+" "+str(f.props._SceneChangeNext)+"\n")
		sl_file.close()
	return clip

HauteurCropBox = HauteurCropBox + DimensionCropBox[1]
if HauteurCropBoxAlt >= 0:
	HauteurCropBoxAlt = HauteurCropBoxAlt + DimensionCropBox[1]

ClipResized = Resizing(Clip, DimensionCropBox[0], DimensionCropBox[1], HauteurCropBox)

Blackclip = core.std.BlankClip(width=int(ClipResized.width-20), height=int(ClipResized.height-20), format=vs.GRAY8, color=0)
Rect = core.std.AddBorders(clip=Blackclip, left=10, right=10, top=10, bottom=10, color=255)
Blank = core.std.BlankClip(ClipResized, format=vs.GRAY8)

ClipCleaned = Cleaning(ClipResized, ExpandRatio)

sc_file = open("SceneChanges.log", "w")
sc_file.write("0 1 0\n")
sc_file.close()
ClipCleanedSC = core.std.CropAbs(clip=ClipCleaned, 
	width=int(ClipCleaned.width/2.7),
	height=int(ClipCleaned.height/2.7),
	left=int(ClipCleaned.width*(1-1/2.7)/2),
	top=int(ClipCleaned.height/2))
ClipCleanedSC = core.misc.SCDetect(clip=ClipCleanedSC, threshold=SeuilSCD)
ClipCleaned = core.std.FrameEval(ClipCleaned, functools.partial(SceneLog, clip=ClipCleaned, log="SceneChanges.log"), prop_src=ClipCleanedSC)

if HauteurCropBoxAlt >= 0:
	ClipResizedAlt = Resizing(Clip, DimensionCropBox[0], DimensionCropBox[1], HauteurCropBoxAlt)

	ClipCleanedAlt = Cleaning(ClipResizedAlt, ExpandRatio)

	sc_file = open("SceneChangesAlt.log", "w")
	sc_file.write("0 1 0\n")
	sc_file.close()
	ClipCleanedAltSC = core.std.CropAbs(clip=ClipCleanedAlt,
		width=int(ClipCleanedAlt.width/2.7),
		height=int(ClipCleanedAlt.height/2.7),
		left=int(ClipCleanedAlt.width*(1-1/2.7)/2),
		top=int(ClipCleanedAlt.height*(1/2-1/2.7)))
	ClipCleanedAltSC = core.misc.SCDetect(clip=ClipCleanedAltSC, threshold=SeuilSCD)
	ClipCleanedAlt = core.std.FrameEval(ClipCleanedAlt, functools.partial(SceneLog, clip=ClipCleanedAlt, log="SceneChangesAlt.log"), prop_src=ClipCleanedAltSC)

	Clip = core.std.StackVertical([ClipCleanedAlt, ClipCleaned])

else:
	if os.path.exists("SceneChangesAlt.log"):
		os.remove("SceneChangesAlt.log")
	Clip = ClipCleaned

Clip.set_output()
