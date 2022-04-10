# QCHack 2022 Amazon Braket Challenge

import pennylane as qml
from pennylane import numpy as np
from qiskit_optimization import QuadraticProgram

'''
Class backend: Define the necessary backend that can interpret pennylane for a Qnode
'''

class backend():
    def __init__(self,wires:int=4,shots:int=10):
        self.wires = wires  
        self.shots = shots

    '''
    Create a QNode with similation from amazon braket, noise model  from pennylane
    Args:
      wires: number of wires of the quantum circuit
      shots: number of shots of the backend
    Returns:
      The device that works in the quantum circuit
    '''

    #method to use the simulation using in amazon braket
    def simulation_model(self):
        return qml.device("braket.local.qubit", wires=self.wires,shots=self.shots)

    
    # using a noise model from pennylane method
    #TODO:design a general noisemodel as args
    #the polaritazion and readouterror
    #this works in pennylane
    def noise_model(self):
        noise_gate = qml.PhaseDamping
        noise_strength = 0.1
        return qml.transforms.insert(noise_gate, noise_strength)(qml.device("default.mixed", wires=self.wires,shots=self.shots))

# example:
# backend(wires=wires,shots=shots)


"""
Class qaoa_convert: generate the methods  to solve the QUBO using QAOA
in pennylane
"""

class qaoa_convert():
    
    def __init__(self,qubo: QuadraticProgram=None,params=None,p:int=1,shots:int=10,backend_name:str ="simulation"): 
        """
        Create the QAOA circuit from a QUBO and its gammas and beta values,
        with a certain level of depth.
        Args:
            qubo: The quadratic program instance
            params: The list of float values that keeps the gammas and beta values
            p: The integer number of layers in the QAOA circuit
            shots: The integer number of shots for the backend
            backend_name: Corresponding the string name of the backend to works
            the QAOA algorithm, has 2 options: 'simulation','noise'
            
        Returns:
            A dict the kepps the measurement of the QAOA circuit
            on all the states with a probability different to 0.
        """
        #number of wires of the quantum circuit
        wires = len(qubo.variables)
        
        #save qubo for future methods
        self.qubo = qubo
        
        #separate the total parameters between gammas and betas
        #consider that those are the same number of variables
        
        nvars = len(params)//2
        gammas = params[:nvars]
        betas = params[nvars:]
        
        #called the qnode for the device
        def circuit(*args, **kwargs):

            #Method to design the quantum circuit 
            
            #obtain the values for our qubo input
            #there are the quadratic and linear coeffs.
            qubo_matrix = qubo.objective.quadratic.to_array(symmetric=True)
            qubo_linearity = qubo.objective.linear.to_array()

            #Apply the initial layer of Hadamard gates to all qubits
            for w in range(wires):
                qml.Hadamard(wires=w)

            #Outer loop to create each layer
            for i in range(p):

                #Apply R_Z rotational gates from cost layer
                for j in range(wires):
                    qml.RZ((qubo_linearity[j] + np.sum(qubo_matrix[j])), wires=j)
                #Apply R_ZZ rotational gates for entangled qubit rotations from cost layer
                for j in range(wires-1):
                    for k in range(j+1,wires):
                          #equivalence of R_ZZ is posible using CNOT,RZ,CNOT
                          qml.CNOT(wires=[k,j])
                          qml.RZ(qubo_matrix[j,k]*gammas[i]*0.5, wires=j)
                          qml.CNOT(wires=[k,j])

                # Apply single qubit X - rotations with angle 2*beta_i to all qubits
                for s in range(wires):
                    qml.RX(2*betas[i],wires=s)
   
            #obtain the probabilities of all the quantum circuit
            return qml.probs(wires=[i for i in range(wires)])
        
        # obtain the list of the state with more probabilities
        # is important indicate the backend to work using the parameter
        # backend_name.
        #for example 
        def probs(*qnode_args, **qnode_kwargs):

            #init the backend instance consider the number of wires,
            #and the number of shots, default values is 10 shots.
            device = backend(wires=wires,shots=shots)
            
            #using the variable pv or probabilities vector to save
            #the result of the quantum circuit.
            pv = []

            #when choose the option 'simulation' indicate to work
            #with the amazon backend
            if backend_name == "simulation":
                ideal_qnode = qml.QNode(circuit, device.simulation_model())
                pv = ideal_qnode().numpy()
            
            #when choose the option 'noise' indicate to work
            #with a basic noise model of pennylane tutorial example 
            elif backend_name == "noise":
                noisy_qnode = qml.QNode(circuit, device.noise_model())
                pv = noisy_qnode().numpy()
            
            # when choose other option is an error but we return a dict
            # with a default value of {0:0}
            else:
                print("You choose only 2 options: simulation,noise")
                print("try again with a valid option")
                return {'0':0}

            #the format output is not a vector, instead of the variable
            #is a dict for that te dict variable keep the final states
            #different to zero value.
            dict_pv = {}  

            #did a iteration with the list values and its index of the
            # probabilities vector variable, all the size depends of the
            #number of wires, for consequence works with 2**wires
            #the elements is the state value 
            for elements in  zip(pv, range(int(2**wires)) ):
                
                #obtain the binary number from the index position with the format 0b000, with [:2] remove the values 0b
                key = (bin(elements[1])[2:])
                
                # all the keys needs the same lenght that is equal to number of qubits
                while len(key) < wires: 
                    #add 0 in case the lenght is less than number of qubits  
                    key = "0"+key
                
                #only save in the dict when the probability is different to 0
                if elements[0] != 0:
                    # mapping the index value in a bin number and into a key for the fict
                    dict_pv[key[::-1]] = elements[0].tolist()  
            
            #return the dict with all the values following the format
            #{'00...0':1,'00...1':1, ... ,'11...1':1}
            return dict_pv

        #in measurement save the dict values of the probs method
        self.measurement = probs()
        
        
   
    #method called probs the proposal return the dict after the measurement
    #of the quantum circuit
    def probs(self):
        # return the state with more probability
        return self.measurement 
    
    #define the cost function using the probability dict to check the
    # correct values with respect the qubo object
    def cost(self):
        
        # init the samples and the cost variables
        samples = 0
        cost = 0
        
        # iter on all the dict called self.measurement
        for sample in list(self.measurement.keys()):
            
            # check the probs with respect the objective value
            #incase of not is correct icnrease the cost
            cost += self.measurement[sample] * self.qubo.objective.evaluate([int(_) for _ in sample])
            samples += self.measurement[sample]
        
        #return the cost value
        return cost 
      
# example:
# wires= len(qubo.variables)
# gammas = np.linspace(0, 2*np.pi, wires)
# betas = np.linspace(0, np.pi, wires)
# p = 2
# shots = 10

# q =qaoa_convert(qubo,gammas,betas,p,shots,backend_name="noise")
