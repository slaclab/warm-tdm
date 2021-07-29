def sq1Flux(group,row,bias):
	low = group.Sq1FbLowOffset.get()
	high = group.Sq1FbHighOffset.get()
	step = group.Sq1FbStepSize.get()
	
	curve = Curve(bias)
	for fb in np.arange(low,high + step,step):
		return
	while fb <= group.Sq1FbHighOffset.get(): #some set of fb
		data.append(SaOffset(group,fb,row))
		fb += group.Sq1FbStepSize.get()
	return data

def sq1FluxRow(group,sq1Bias):
	for row in range(group.NumRows.get()):
		group.fasBias[row].set(on)  #At what level will this be stored
		group.SaFb[row].set() #does this come from a config file
	results = sq1Flux(group)

def sq1FluxRowBias(group):
	pass
	

def sq1Tune(group):
	sq1FluxRowBiasResults = sq1FluxRowBias(group)
	for row in range(group.NumRows.get()): 
		#Record sq1 bias value which results in the max peak to peak in the sq1 flux curve
		data = sq1FluxRowBias()
		#record sq1 fb value at the midpoint between high and low point in the sq1flux curve
		#This is done within the class
	
	return #?

def sq1Flux(group):
	pass
def sq1FluxRow(group,sq1Bias):
	something = Curve(sq1Bias)

	for row in range(group.NumRows.get()):
		group.FasFlux.set(group.FasFluxOn)

def sq1FluxRowBias(group):
	low = group.Sq1BiasLowOffset.get()
	high = group.Sq1BiasHighOffset.get()
	step = group.Sq1BiasStepSize.get()
	
	data.populateXValues(low,high + step,step)

	data = CurveData()

	for sq1Bias in np.arange(low,high + step,step):
		data.addCurve(sq1FluxRow(group,sq1Bias)) #with offset as a function of sq1FB, with each curve being a different Sq1Bias
	
	data.update()

	return data


def sq1Tune(group):
	for row in range(group.NumRows.get()):
		group.
	data = sq1FluxRowBias()

	for row in range(group.NumRows.get()): #or maybe for row in a list of curvedata objects
		pass
		#record sq1Bias value which results in the largest peak to peak value in the sq1Flux curve
		#record sq1Fb value at the midpoint between a high and low point in the chosen sq1flux curve
		#these are both done by the class
