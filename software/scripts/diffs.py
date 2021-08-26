17c17
< #pid loop 
---
> #pid loop
39c39
< def saOffset(group,row,column,precision=1): #put the column loop in here 
---
> def saOffset(group,row,column,precision=1): #put the column loop in here
43c43
<     lower = -100 
---
>     lower = -100
53c53
<                    precision=precision)
---
>                    precision=precision))
60c60
<     Iterates through SaFb values determined by lowoffset,highoffset,step and 
---
>     Iterates through SaFb values determined by lowoffset,highoffset,step and
85c85
<             group.SaFb.set(index=(row,col),value=saFbOffsetRange[col][idx])
---
>             group.SaFb.set(index=(col,row),value=saFbOffsetRange[col][idx])
99c99
<     step and calls saFlux to generate curves, adding them 
---
>     step and calls saFlux to generate curves, adding them
135c135
<      is plotted against SaFb values, which each curve 
---
>      is plotted against SaFb values, which each curve
150,151c150,151
<     """Returns list of SaFb values which zero out SaOut. 
<     Each element corresponds with a column 
---
>     """Returns list of SaFb values which zero out SaOut.
>     Each element corresponds with a column
165c165
<     return colresults 
---
>     return colresults
169c169
<     Iterates through FasFluxOn values determined by 
---
>     Iterates through FasFluxOn values determined by
184c184
<        
---
> 
191,193c191,193
<             
<             curve.addPoint(saFbResults[col]) #Confused about this
<         
---
> 
>             curve.addPoint(saFbResults[col])
> 
203c203
<     accordingly. 
---
>     accordingly.
226c226
< #SQ1 TUNING - output vs sq1fb for various values of sq1 bias for every row for every column 
---
> #SQ1 TUNING - output vs sq1fb for various values of sq1 bias for every row for every column
232a233,234
>     Sq1FbOffsetRange = []
> 
236c238,239
<         step = group.Sq1FbStepSize.get()
---
>         numsteps = group.Sq1FbNumSteps.get()
>         Sq1FbOffsetRange.append(np.linspace(low,high,numsteps,endpoint=True))
237a241,254
>     for col in range(len(group.ColMap.get())):
>         curves.append(cc.Curve(bias))
> 
>     for idx in range(len(Sq1FbOffsetRange[0])):
>         for col in range(len(group.ColMap.get)):
>             group.Sq1Fb.set((index=col,row),value=Sq1FbOffsetRange[col][idx])
>         points = saOffset(group,row)
> 
>         for col in range(len(group.ColMap.get())):
>             curves[col].addPoint(points[col])
>     return curves
>     
>     ###OLD CODE BELOW
>     for col in range(len(group.ColMap.get())):
247c264
<     """Returns Curve object. 
---
>     """Returns Curve object.
255c272
<         #set the corresponding saFb value for the row (wouldn't they already have been set?) 
---
>         #set the corresponding saFb value for the row (wouldn't they already have been set?)
274c291
<         stepFb= group.Sq1FbStepSize.get() 
---
>         stepFb= group.Sq1FbStepSize.get()
277c294
<         data.populateXValues(lowFb,highFb+stepFb,stepFb) 
---
>         data.populateXValues(lowFb,highFb+stepFb,stepFb)
297c314
<         list of CurveData objects where saOffset subroutine result 
---
>         list of CurveData objects where saOffset subroutine result
299c316
<         sq1Bias, and each CurveData object in the list corresponds 
---
>         sq1Bias, and each CurveData object in the list corresponds
318,319c335,336
<     """Returns list of offsets that zero out SaOut depending 
<     on the biasIterates through Sq1Fb values determined by 
---
>     """Returns list of offsets that zero out SaOut depending
>     on the biasIterates through Sq1Fb values determined by
368,369d384
< 
< 
