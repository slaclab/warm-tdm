def sq1flux(group,row,bias):
	low = group.Sq1fbLowOfset.get()
	high = group.Sq1fbHighOfset.get()
	step = group.Sq1fbStepSize.get()
	
	curve = Curve(bias)
	for fb in np.arange(low,high + step,step):
		return
	while fb <= group.Sq1fbHighOfset.get(): #some set of fb
		data.append(SaOfset(group,fb,row))
		fb += group.Sq1fbStepSize.get()
	return data


#will need to set certain things
def sq1fluxRow(group,sq1Bias):
	for row in range(group.NumRows.get()):
		group.fasBias[row].set(on)  #At what level will this be stored
		group.Safb[row].set() #does this come from a config file
	results = sq1flux(group)

def sq1fluxRowBias(group):
	pass
	
def sq1Tune(group):
	sq1fluxRowBiasResults = sq1fluxRowBias(group)
	for row in range(group.NumRows.get()): 
		#Record sq1 bias value which results in the max peak to peak in the sq1 flux curve
		data = sq1fluxRowBias()
		#record sq1 fb value at the midpoint between high and low point in the sq1flux curve
		#This is done within the class
	
	return #?

def sq1flux(group):
	pass
def sq1fluxRow(group,sq1Bias):
	something = Curve(sq1Bias)

	for row in range(group.NumRows.get()):
		group.fasflux.set(group.fasfluxOn)

def sq1fluxRowBias(group):
	low = group.Sq1BiasLowOfset.get()
	high = group.Sq1BiasHighOfset.get()
	step = group.Sq1BiasStepSize.get()
	
	data.populateXValues(low,high + step,step)

	data = CurveData()

	for sq1Bias in np.arange(low,high + step,step):
		data.addCurve(sq1fluxRow(group,sq1Bias)) #with ofset as a function of sq1fB, with each curve being a diferent Sq1Bias
	
	data.update()

	return data


def sq1Tune(group):
	for row in range(group.NumRows.get()):
		group.
	data = sq1fluxRowBias()

	for row in range(group.NumRows.get()): #or maybe for row in a list of curvedata objects
		pass
		#record sq1Bias value which results in the largest peak to peak value in the sq1flux curve
		#record sq1fb value at the midpoint between a high and low point in the chosen sq1flux curve
		#these are both done by the class
