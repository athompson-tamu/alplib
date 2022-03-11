# ALP Fluxes, DM Fluxes
# All fluxes in cm^-2 s^-1 or cm^-2 s^-1 MeV^-1


from .constants import *
from .fmath import *
from .materials import *
from .decay import *
from .prod_xs import *
from .det_xs import *
from .photon_xs import *
from .matrix_element import *
from .cross_section_mc import *




class AxionFlux:
    # Generic superclass for constructing fluxes
    def __init__(self, axion_mass, target: Material, det_dist, det_length, det_area, n_samples=1000):
        self.ma = axion_mass
        self.target_z = target.z[0]  # TODO: take z array for compound mats
        self.target_a = target.z[0] + target.n[0]
        self.target_density = target.density
        self.det_dist = det_dist  # meters
        self.det_length = det_length  # meters
        self.det_area = det_area  # square meters
        self.axion_energy = []
        self.axion_angle = []
        self.axion_flux = []
        self.decay_axion_weight = []
        self.scatter_axion_weight = []
        self.n_samples = n_samples
    
    def det_sa(self):
        return arctan(sqrt(self.det_area / pi) / self.det_dist)
    
    def propagate(self, decay_width, rescale_factor=1.0):
        e_a = np.array(self.axion_energy)
        wgt = np.array(self.axion_flux)

        # Get axion Lorentz transformations and kinematics
        p_a = sqrt(e_a**2 - self.ma**2)
        v_a = p_a / e_a
        boost = e_a / self.ma
        tau = boost / decay_width if decay_width > 0.0 else np.inf * np.ones_like(boost)

        # Get decay and survival probabilities
        surv_prob = np.array([np.exp(-self.det_dist / METER_BY_MEV / v_a[i] / tau[i]) \
                     for i in range(len(v_a))])
        decay_prob = np.array([(1 - np.exp(-self.det_length / METER_BY_MEV / v_a[i] / tau[i])) \
                      for i in range(len(v_a))])

        self.decay_axion_weight = np.asarray(rescale_factor * wgt * surv_prob * decay_prob, dtype=np.float32)
        self.scatter_axion_weight = np.asarray(rescale_factor * wgt * surv_prob, dtype=np.float32)
    
    def propagate_iso_vol_int(self, geom: DetectorGeometry, decay_width, rescale_factor=1.0):
        e_a = np.array(self.axion_energy)
        wgt = np.array(self.axion_flux)

        # Get axion Lorentz transformations and kinematics
        p_a = sqrt(e_a**2 - self.ma**2)
        v_a = p_a / e_a
        boost = e_a / self.ma
        tau = boost / decay_width if decay_width > 0.0 else np.inf * np.ones_like(boost)

        surv_prob = np.array([np.exp(-self.det_dist / METER_BY_MEV / v_a[i] / tau[i]) \
                     for i in range(len(v_a))])

        vol_integrals = []
        for i in range(len(e_a)):
            # Integrate over the detector volume with weight function P_decay / (4*pi*l^2)
            # where l is the distance to the source from the volume element
            f = lambda x : (1 / METER_BY_MEV / v_a[i] / tau[i]) \
                * np.exp(-x / METER_BY_MEV / v_a[i] / tau[i]) / (4*pi*x**2)
            vol_integrals.append(geom.integrate(f_int=f))
        
        self.decay_axion_weight = np.asarray(rescale_factor * wgt * np.array(vol_integrals), dtype=np.float32)
        self.scatter_axion_weight = np.asarray(rescale_factor * wgt * surv_prob, dtype=np.float32)




class FluxPrimakoff(AxionFlux):
    # Generator for ALP flux from 2D photon spectrum (E_\gamma, \theta_\gamma)
    def __init__(self, axion_mass, target_z, det_z, det_dist, det_length, det_area, n_samples=1000):
        super().__init__(axion_mass, target_z, det_z, det_dist, det_length, det_area, n_samples)
    
    def decay_width(self):
        pass

    def simulate_single(self):
        pass

    def simulate(self):
        pass




class FluxPrimakoffIsotropic(AxionFlux):
    """
    Generator for Primakoff-produced axion flux
    Takes in a flux of photons
    """
    def __init__(self, photon_flux=[1,1], target=Material("W"), det_dist=4.0, det_length=0.2,
                    det_area=0.04, axion_mass=0.1, axion_coupling=1e-3, n_samples=1000):
        super().__init__(axion_mass, target, det_dist, det_length, det_area)
        self.photon_flux = photon_flux
        self.gagamma = axion_coupling
        self.n_samples = n_samples
        self.target_photon_xs = AbsCrossSection(target)

    def decay_width(self, gagamma, ma):
        return W_gg(gagamma, ma)
    
    def photon_flux_dN_dE(self, energy):
        return np.interp(energy, self.photon_flux[:,0], self.photon_flux[:,1], left=0.0, right=0.0)

    def simulate_single(self, photon):
        gamma_energy = photon[0]
        gamma_wgt = photon[1]
        if gamma_energy < self.ma:
            return

        xs = primakoff_sigma(gamma_energy, self.gagamma, self.ma, self.target_z)
        br = xs / self.target_photon_xs.sigma_mev(gamma_energy)
        self.axion_energy.append(gamma_energy)
        self.axion_flux.append(gamma_wgt * br)

    def simulate(self):
        self.axion_energy = []
        self.axion_flux = []
        self.scatter_axion_weight = []
        self.decay_axion_weight = []

        for i, el in enumerate(self.photon_flux):
            self.simulate_single(el)
    
    def propagate(self, new_coupling=None):
        if new_coupling is not None:
            rescale=power(new_coupling/self.gagamma, 2)
            super().propagate(W_gg(new_coupling, self.ma), rescale)
        else:
            super().propagate(W_gg(self.gagamma, self.ma))
        geom_accept = self.det_area / (4*pi*self.det_dist**2)
        self.decay_axion_weight *= geom_accept
        self.scatter_axion_weight *= geom_accept




class FluxCompton(AxionFlux):
    # Generator for ALP flux from 2D photon spectrum (E_\gamma, \theta_\gamma)
    def __init__(self, axion_mass, target: Material, det_dist, det_length, det_area, n_samples=1000):
        super().__init__(axion_mass, target, det_dist, det_length, det_area, n_samples)

    def simulate_single(self):
        pass

    def simulate(self):
        pass




class FluxComptonIsotropic(AxionFlux):
    """
    Generator for axion flux from compton-like scattering
    Takes in a flux of photons
    """
    def __init__(self, photon_flux=[1,1], target=Material("W"), det_dist=4.,
                    det_length=0.2, det_area=0.04, axion_mass=0.1, axion_coupling=1e-3, n_samples=100,
                    is_isotropic=True):
        super().__init__(axion_mass, target, det_dist, det_length, det_area)
        self.photon_flux = photon_flux
        self.ge = axion_coupling
        self.n_samples = n_samples
        self.target_photon_xs = AbsCrossSection(target)
        self.is_isotropic = is_isotropic
    
    def decay_width(self, ge, ma):
        return W_ee(ge, ma)

    def simulate_single(self, photon):
        gamma_energy = photon[0]
        gamma_wgt = photon[1]

        s = 2 * M_E * gamma_energy + M_E ** 2
        if s < (M_E + self.ma)**2:
            return

        ea_rnd = np.random.uniform(self.ma, gamma_energy, self.n_samples)
        mc_xs = (gamma_energy - self.ma) * compton_dsigma_dea(ea_rnd, gamma_energy, self.ge, self.ma, self.target_z) / self.n_samples
        diff_br = mc_xs / self.target_photon_xs.sigma_mev(gamma_energy)

        for i in range(self.n_samples):
            self.axion_energy.append(ea_rnd[i])
            self.axion_flux.append(gamma_wgt * diff_br[i])

    def simulate(self):
        self.axion_energy = []
        self.axion_flux = []
        self.scatter_axion_weight = []
        self.decay_axion_weight = []

        for i, el in enumerate(self.photon_flux):
            self.simulate_single(el)
    
    def propagate(self, new_coupling=None):
        if new_coupling is not None:
            super().propagate(W_ee(new_coupling, self.ma), rescale_factor=power(new_coupling/self.ge, 2))
        else:
            super().propagate(W_ee(self.ge, self.ma))
        
        if self.is_isotropic:
            geom_accept = self.det_area / (4*pi*self.det_dist**2)
            self.decay_axion_weight *= geom_accept
            self.scatter_axion_weight *= geom_accept




def track_length_prob(Ei, Ef, t):
    b = 4/3
    return heaviside(Ei-Ef, 0.0) * abs(power(log(Ei/Ef), b*t - 1) / (Ei * gamma(b*t)))




class FluxBremIsotropic(AxionFlux):
    """
    Generator for axion-bremsstrahlung flux
    Takes in a flux of el
    """
    def __init__(self, electron_flux=[1.,0.], positron_flux=[1.,0.], target=Material("W"),
                    target_density=19.3, target_radiation_length=6.76, target_length=10.0, det_dist=4., det_length=0.2,
                    det_area=0.04, axion_mass=0.1, axion_coupling=1e-3, n_samples=100, is_isotropic=True):
        super().__init__(axion_mass, target, det_dist, det_length, det_area)
        # TODO: Replace A = 2*Z with real numbers of nucleons
        self.electron_flux = electron_flux
        self.positron_flux = positron_flux
        self.ge = axion_coupling
        self.target_density = target_density  # g/cm3
        self.target_radius = target_length  # cm
        self.ntargets_by_area = target_length * target_density * AVOGADRO / (2*target.z[0])  # N_T / cm^2
        self.ntarget_area_density = target_radiation_length * AVOGADRO / (2*target.z[0])
        self.n_samples = n_samples
        self.is_isotropic = is_isotropic
    
    def decay_width(self):
        return W_ee(self.ge, self.ma)
    
    def electron_flux_dN_dE(self, energy):
        return np.interp(energy, self.electron_flux[:,0], self.electron_flux[:,1], left=0.0, right=0.0)
    
    def positron_flux_dN_dE(self, energy):
        return np.interp(energy, self.positron_flux[:,0], self.positron_flux[:,1], left=0.0, right=0.0)
    
    def electron_flux_attenuated(self, t, E0, E1):
        return (self.electron_flux_dN_dE(E0) + self.positron_flux_dN_dE(E0)) * track_length_prob(E0, E1, t)

    def simulate_single(self, electron):
        el_energy = electron[0]
        el_wgt = electron[1]

        ea_max = el_energy * (1 - power(self.ma/el_energy, 2))
        #ea_max = el_energy
        if ea_max < self.ma:
            return

        ea_rnd = np.random.uniform(self.ma, ea_max, self.n_samples)
        mc_vol = (ea_max - self.ma)/self.n_samples
        diff_br = (self.ntarget_area_density * HBARC**2) * mc_vol * brem_dsigma_dea(ea_rnd, el_energy, self.ge, self.ma, self.target_z)

        for i in range(self.n_samples):
            self.axion_energy.append(ea_rnd[i])
            self.axion_flux.append(el_wgt * diff_br[i])

    def simulate(self):
        self.axion_energy = []
        self.axion_flux = []
        self.scatter_axion_weight = []
        self.decay_axion_weight = []

        for i, el in enumerate(self.electron_flux):
            self.simulate_single(el)
    
    def propagate(self, new_coupling=None):
        if new_coupling is not None:
            super().propagate(W_ee(new_coupling, self.ma), rescale_factor=power(new_coupling/self.ge, 2))
        else:
            super().propagate(W_ee(self.ge, self.ma))
        
        if self.is_isotropic:
            geom_accept = self.det_area / (4*pi*self.det_dist**2)
            self.decay_axion_weight *= geom_accept
            self.scatter_axion_weight *= geom_accept




class FluxResonanceIsotropic(AxionFlux):
    """
    Generator for e+ e- resonant ALP production flux
    Takes in a flux of positrons
    """
    def __init__(self, positron_flux=[1.,0.], target=Material("W"), target_length=10.0,
                 target_radiation_length=6.76, det_dist=4., det_length=0.2, det_area=0.04,
                 axion_mass=0.1, axion_coupling=1e-3, n_samples=100, is_isotropic=True):
        # TODO: make flux take in a Detector class and a Target class (possibly Material class?)
        # Replace A = 2*Z with real numbers of nucleons
        super().__init__(axion_mass, target, det_dist, det_length, det_area, n_samples)
        self.positron_flux = positron_flux  # differential positron energy flux dR / dE+ / s
        self.positron_flux_bin_widths = positron_flux[1:,0] - positron_flux[:-1,0]
        self.ge = axion_coupling
        self.target_radius = target_length  # cm
        self.ntarget_area_density = target_radiation_length * AVOGADRO / (2*target.z[0])  # N_T / cm^2
        self.is_isotropic = is_isotropic
    
    def decay_width(self):
        return W_ee(self.ge, self.ma)
    
    def positron_flux_dN_dE(self, energy):
        return np.interp(energy, self.positron_flux[:,0], self.positron_flux[:,1], left=0.0, right=0.0)
    
    def positron_flux_attenuated(self, t, energy_pos, energy_res):
        return self.positron_flux_dN_dE(energy_pos) * track_length_prob(energy_pos, energy_res, t)

    def simulate(self):
        self.axion_energy = []
        self.axion_flux = []
        self.scatter_axion_weight = []
        self.decay_axion_weight = []

        resonant_energy = -M_E + self.ma**2 / (2 * M_E)
        if resonant_energy + M_E < self.ma:
            return
        
        if resonant_energy < M_E:
            return
        
        if resonant_energy > max(self.positron_flux[:,0]):
            return
        
        e_rnd = np.random.uniform(resonant_energy, max(self.positron_flux[:,0]), self.n_samples)
        t_rnd = np.random.uniform(0.0, 5.0, self.n_samples)
        mc_vol = (5.0 - 0.0)*(max(self.positron_flux[:,0]) - resonant_energy)

        attenuated_flux = mc_vol*np.sum(self.positron_flux_attenuated(t_rnd, e_rnd, resonant_energy))/self.n_samples
        wgt = self.target_z * (self.ntarget_area_density * HBARC**2) * resonance_peak(self.ge) * attenuated_flux
        
        self.axion_energy.append(self.ma**2 / (2 * M_E))
        self.axion_flux.append(wgt)
    
    def propagate(self, new_coupling=None):
        if new_coupling is not None:
            super().propagate(W_ee(new_coupling, self.ma), rescale_factor=power(new_coupling/self.ge, 2))
        else:
            super().propagate(W_ee(self.ge, self.ma))
        
        if self.is_isotropic:
            geom_accept = self.det_area / (4*pi*self.det_dist**2)
            self.decay_axion_weight *= geom_accept
            self.scatter_axion_weight *= geom_accept




class FluxPairAnnihilationIsotropic(AxionFlux):
    """
    Generator associated production via electron-positron annihilation
    (e+ e- -> a gamma)
    Takes in a flux of positrons
    """
    def __init__(self, positron_flux=[1.,0.], target=Material("W"),
                 target_radiation_length=6.76, det_dist=4., det_length=0.2, det_area=0.04,
                 axion_mass=0.1, axion_coupling=1e-3, n_samples=100, is_isotropic=True):
        # TODO: make flux take in a Detector class and a Target class (possibly Material class?)
        # Replace A = 2*Z with real numbers of nucleons
        super().__init__(axion_mass, target, det_dist, det_length, det_area, n_samples)
        self.positron_flux = positron_flux  # differential positron energy flux dR / dE+ / s
        self.positron_flux_bin_widths = positron_flux[1:,0] - positron_flux[:-1,0]
        self.ge = axion_coupling
        self.ntarget_area_density = target_radiation_length * AVOGADRO / (2*target.z[0])
        self.is_isotropic = is_isotropic
    
    def decay_width(self):
        return W_ee(self.ge, self.ma)
    
    def simulate_single(self, positron):
        ep_lab = positron[0]
        pos_wgt = positron[1]

        if ep_lab < max((self.ma**2 - M_E**2)/(2*M_E), M_E):
            # Threshold check
            return

        # Simulate ALPs produced in the CM frame
        cm_cosines = np.random.uniform(-1, 1, self.n_samples)
        cm_wgts = (self.ntarget_area_density * HBARC**2) * associated_dsigma_dcos_CM(cm_cosines, ep_lab, self.ma, self.ge, self.target_z)

        # Boost the ALPs to the lab frame and multiply weights by jacobian for the boost
        jacobian_cm_to_lab = power(2, 1.5) * power(1 + cm_cosines, 0.5)
        ea_cm = sqrt(M_E * (ep_lab + M_E) / 2)
        paz_cm = sqrt(M_E * (ep_lab + M_E) / 2 - self.ma**2) * cm_cosines
        beta = sqrt(ep_lab**2 - M_E**2) / (M_E + ep_lab)
        gamma = power(1-beta**2, -0.5)

        # Get the lab frame energy distribution
        ea_lab = gamma*(ea_cm + beta*paz_cm)
        mc_volume = 2 / self.n_samples  # we integrated over cosThetaLab from -1 to 1

        for i in range(self.n_samples):
            self.axion_energy.append(ea_lab[i])
            self.axion_flux.append(pos_wgt * jacobian_cm_to_lab[i] * cm_wgts[i] * mc_volume)

    
    def simulate(self):
        self.axion_energy = []
        self.axion_flux = []
        self.scatter_axion_weight = []
        self.decay_axion_weight = []

        for i, el in enumerate(self.positron_flux):
            self.simulate_single(el)

    def propagate(self, new_coupling=None):
        if new_coupling is not None:
            super().propagate(W_ee(new_coupling, self.ma), rescale_factor=power(new_coupling/self.ge, 2))
        else:
            super().propagate(W_ee(self.ge, self.ma))
        
        if self.is_isotropic:
            geom_accept = self.det_area / (4*pi*self.det_dist**2)
            self.decay_axion_weight *= geom_accept
            self.scatter_axion_weight *= geom_accept




class FluxNuclearIsotropic(AxionFlux):
    """
    Takes in a rate (#/s) of nuclear decays for a specified nuclear transition
    Produces the associated ALP flux from a given branching ratio
    """
    def __init__(self, transition_rates=np.array([[1.0, 0.0]]), target=Material("W"),
                 det_dist=4., det_length=0.2, det_area=0.04, is_isotropic=True,
                 axion_mass=0.1, gae=1.0e-5, gann0=1e-3, gann1=1e-3, n_samples=100):
        super().__init__(axion_mass, target, det_dist, det_length, det_area, n_samples)
        self.rates = transition_rates
        self.gann0 = gann0
        self.gann1 = gann1
        self.gae = gae
        self.is_isotropic = is_isotropic

    def br(self, energy, j=1, delta=0.0, beta=1.0, eta=0.5):
        mu0 = 0.88
        mu1 = 4.71
        return ((j/(j+1)) / (1 + delta**2) / pi / ALPHA) \
            * power(sqrt(energy**2 - self.ma**2)/energy, 2*j + 1) \
                * power((self.gann0 * beta + self.gann1)/((mu0-0.5)*beta + (mu1 - eta)), 2)

    def simulate(self, j=1, delta=0.0, beta=1.0, eta=0.5):
        self.axion_energy = []
        self.axion_flux = []
        self.scatter_axion_weight = []
        self.decay_axion_weight = []

        for i in range(self.rates.shape[0]):
            self.axion_energy.append(self.rates[i,0])
            self.axion_flux.append(self.rates[i,1] * self.br(self.rates[i,0], j, delta, beta, eta))

    def propagate(self, new_coupling=None):
        if new_coupling is not None:
            rescale=power(new_coupling/self.gae, 2)
            super().propagate(W_ee(new_coupling, self.ma), rescale)
        else:
            super().propagate(W_ee(self.gae, self.ma))
        
        if self.is_isotropic:
            geom_accept = self.det_area / (4*pi*self.det_dist**2)
            self.decay_axion_weight *= geom_accept
            self.scatter_axion_weight *= geom_accept
    
    def propagate_iso_vol_int(self, geom: DetectorGeometry, new_coupling=None):
        if new_coupling is not None:
            rescale=power(new_coupling/self.gagamma, 2)
            super().propagate_iso_vol_int(geom, W_gg(self.gagamma, self.ma), rescale)
        else:
            super().propagate_iso_vol_int(geom, W_gg(self.gagamma, self.ma))




class FluxChargedMeson3BodyDecay(AxionFlux):
    def __init__(self, meson_flux, axion_mass=0.1, coupling=1.0, n_samples=50, meson_type="pion",
                 m_lepton=M_MU, boson_type="S", energy_cut=140.0, det_dist=541, det_length=12, det_area=36,
                 target=Material("Be")):
        super().__init__(axion_mass, target, det_dist, det_length, det_area, n_samples)
        self.meson_flux = meson_flux
        if meson_type == "pion":
            self.mm = M_PI
            self.ckm = V_UD
            self.fM = F_PI
            self.total_width = PION_WIDTH
        elif meson_type == "kaon":
            self.mm = M_K
            self.ckm = V_US
            self.fM = F_K
            self.total_width = KAON_WIDTH
        else:
            raise Exception("Meson type not understood!", meson_type)
        self.m_lepton = m_lepton
        self.rep = boson_type
        self.gmu = coupling
        self.EaMax = (self.mm**2 + self.ma**2 - self.m_lepton**2)/(2*self.mm)
        self.EaMin = self.ma
        self.dump_dist = 50
        self.det_sa = cos(arctan(self.det_length/(self.det_dist-self.dump_dist)/2))
        self.solid_angles = []
        self.energy_cut = energy_cut
        self.cosines = []
        self.decay_pos = []

    def dGammadEa(self, Ea):
        m212 = self.mm**2 + self.ma**2 - 2*self.mm*Ea
        e2star = (m212 - self.m_lepton**2)/(2*sqrt(m212))
        e3star = (self.mm**2 - m212 - self.ma**2)/(2*sqrt(m212))

        if self.ma > e3star:
            return 0.0

        m223Max = (e2star + e3star)**2 - (sqrt(e2star**2) - sqrt(e3star**2 - self.ma**2))**2
        m223Min = (e2star + e3star)**2 - (sqrt(e2star**2) + sqrt(e3star**2 - self.ma**2))**2
    
        def MatrixElement2P(m223):
            ev = (m212 + m223 - self.m_lepton**2 - self.ma**2)/(2*self.mm)
            emu = (self.mm**2 - m223 + self.m_lepton**2)/(2*self.mm)
            q2 = self.mm**2 - 2*self.mm*ev

            prefactor = heaviside(e3star-self.ma,0.0)*(self.gmu*G_F*self.fM*self.ckm/(q2 - self.m_lepton**2))**2
            return prefactor*((2*self.mm*emu*q2 * (q2 - self.m_lepton**2) - (q2**2 - (self.m_lepton*self.mm)**2)*(q2 + self.m_lepton**2 - self.ma**2)) - (2*q2*self.m_lepton**2 * (self.mm**2 - q2)))
        
        def MatrixElement2S(m223):
            ev = (m212 + m223 - self.m_lepton**2 - self.ma**2)/(2*self.mm)
            emu = (self.mm**2 - m223 + self.m_lepton**2)/(2*self.mm)
            q2 = self.mm**2 - 2*self.mm*ev

            prefactor = heaviside(e3star-self.ma,0.0)*(self.gmu*G_F*self.fM*self.ckm/(q2 - self.m_lepton**2))**2
            return prefactor*((2*self.mm*emu*q2 * (q2 - self.m_lepton**2) - (q2**2 - (self.m_lepton*self.mm)**2)*(q2 + self.m_lepton**2 - self.ma**2)) + (2*q2*self.m_lepton**2 * (self.mm**2 - q2)))

        def MatrixElement2V(m223):
            q2 = self.mm**2 - 2*self.mm*(m212 + m223 - self.m_lepton**2 - self.ma**2)/(2*self.mm)

            prefactor = heaviside(e3star-self.ma,0.0)*8*power(G_F*self.fM*self.ckm/(q2 - self.m_lepton**2)/self.ma, 2)

            lq = (m212 - self.m_lepton**2)/2
            lp = (self.mm**2 - m212 - m223)/2
            kq = (m212 + m223 - self.m_lepton**2 - self.ma**2)/2
            pq = (m223 - self.ma**2)/2
            kl = (self.mm**2 + self.m_lepton**2 - m223)/2
            kp = (self.mm**2 + self.ma**2 - m212)/2

            cr = self.gmu
            cl = self.gmu

            # Dmu(self.mm/kl)*
            return -prefactor * ((power(cr*self.mm*self.m_lepton,2) - power(cl*q2,2)) * (lq*self.ma**2 + 2*lp*pq) \
                - 2*cr*self.m_lepton**2 * kq * (cr*self.ma**2 * kl + 2*cr*kp*lp - 3*cl*q2*self.ma**2))
        
        def MatrixElement2QV(m223):
            kl = (self.mm**2 - m212 - m223)/2
            kq = (m223 - self.ma**2)/2
            lq = (m212 - self.m_lepton**2)/2

            prefactor_IB3 = -2*power(self.gmu * G_F * self.fM * self.m_lepton, 2)
            M_IB3 = -(prefactor_IB3 / self.m_lepton**2) * (8*lq + 16*kl*kq / self.ma**2)

            return M_IB3
        
        if self.rep == "P":
            return (2*self.mm)/(32*power(2*pi*self.mm, 3))*quad(MatrixElement2P, m223Min, m223Max)[0]
        
        if self.rep == "S":
            return (2*self.mm)/(32*power(2*pi*self.mm, 3))*quad(MatrixElement2S, m223Min, m223Max)[0]

        if self.rep == "V":
            return (2*self.mm)/(32*power(2*pi*self.mm, 3))*quad(MatrixElement2V, m223Min, m223Max)[0]
        
        if self.rep == "QV":
            return (2*self.mm)/(32*power(2*pi*self.mm, 3))*quad(MatrixElement2QV, m223Min, m223Max)[0]
    
    def total_br(self):
        EaMax = (self.mm**2 + self.ma**2 - self.m_lepton**2)/(2*self.mm)
        EaMin = self.ma
        return quad(self.dGammadEa, EaMin, EaMax)[0] / self.total_width
    
    def simulate_single(self, meson_p, pion_wgt, cut_on_solid_angle=True, solid_angle_cosine=0.0):
        ea_min = self.ma
        ea_max = (self.mm**2 + self.ma**2 - self.m_lepton**2)/(2*self.mm)

        # Boost to lab frame
        beta = meson_p / sqrt(meson_p**2 + self.mm**2)
        boost = power(1-beta**2, -0.5)

        min_cm_cos = cos(min(boost * arccos(solid_angle_cosine), pi))
        # Draw random variate energies and angles in the pion rest frame
        energies = np.random.uniform(ea_min, ea_max, self.n_samples)
        momenta = sqrt(energies**2 - self.ma**2)
        cosines = np.random.uniform(min_cm_cos, 1, self.n_samples)
        pz = momenta*cosines

        e_lab = boost*(energies + beta*pz)
        pz_lab = boost*(pz + beta*energies)
        cos_theta_lab = pz_lab / sqrt(e_lab**2 - self.ma**2)

        # Jacobian for transforming d2Gamma/(dEa * dOmega) to lab frame:
        jacobian = sqrt(e_lab**2 - self.ma**2) / momenta
        # Monte Carlo volume, making sure to use the lab frame energy range
        mc_vol = (self.EaMax - self.EaMin)*(1-min_cm_cos)
        mc_vol_lab = boost*(self.EaMax - sqrt(self.EaMax**2 - self.ma**2)*beta) - boost*(self.EaMin + sqrt(self.EaMin**2 - self.ma**2)*beta)

        # Draw weights from the PDF
        weights = np.array([pion_wgt*mc_vol*self.dGammadEa(ea)/self.total_width/self.n_samples \
            for ea in energies])
        #weights = np.array([pion_wgt*mc_vol_lab*self.dGammadEa(ea)/self.gamma_sm()/self.n_samples \
        #    for ea in energies])*jacobian

        for i in range(self.n_samples):
            solid_angle_acceptance = heaviside(cos_theta_lab[i] - solid_angle_cosine, 0.0)
            if solid_angle_acceptance == 0.0 and cut_on_solid_angle:
                continue
            self.axion_energy.append(e_lab[i])
            self.cosines.append(cos_theta_lab[i])
            self.axion_flux.append(weights[i]*heaviside(e_lab[i]-self.energy_cut,1.0))
            self.solid_angles.append(solid_angle_cosine)
    
    def simulate(self, cut_on_solid_angle=True):
        self.axion_energy = []
        self.cosines = []
        self.axion_flux = []
        self.scatter_axion_weight = []
        self.decay_axion_weight = []
        self.decay_pos = []
        self.solid_angles = []

        if self.ma > self.mm - self.m_lepton:
            # Kinematically forbidden beyond Meson mass - muon mass difference
            return

        for i, p in enumerate(self.meson_flux):
            # Simulate decay positions between target and dump
            # The quantile is truncated at the dump position via umax
            decay_l = METER_BY_MEV * p[0] / self.gamma_sm() / self.mm
            umax = exp(-2*self.dump_dist/decay_l) * power(exp(self.dump_dist/decay_l) - 1, 2) \
                if decay_l > 1.0 else 1.0
            try:
                u = np.random.uniform(0.0, min(umax, 1.0))
            except:
                print("umax = ", umax, " decay l = ", decay_l, p[0])
            x = decay_quantile(u, p[0], self.mm, self.gamma_sm())
            
            # Append decay positions and solid angle cosines for the geometric acceptance of each meson decay
            self.decay_pos.append(x)
            solid_angle_cosine = cos(arctan(self.det_length/(self.det_dist-x)/2))

            # Simulate decays for each charged meson
            self.simulate_single(p[0], p[2], cut_on_solid_angle, solid_angle_cosine)
        

    def propagate(self, gagamma=None):  # propagate to detector
        wgt = np.array(self.axion_flux)
        # Do not decay
        self.decay_weight = np.asarray(wgt*0.0, dtype=np.float64)
        self.scatter_weight = np.asarray(wgt, dtype=np.float64)




class FluxChargedMeson3BodyIsotropic(AxionFlux):
    def __init__(self, meson_flux=[[0.0, 0.0259]], boson_mass=0.1, coupling=1.0, meson_type="pion",
                 m_lepton=M_MU, boson_type="S", det_dist=20, det_length=2, det_area=2, target=Material("W"),
                 n_samples=50):
        super().__init__(boson_mass, target, det_dist, det_length, det_area, n_samples)
        self.meson_flux = meson_flux
        if meson_type == "pion":
            self.mm = M_PI
            self.ckm = V_UD
            self.fM = F_PI
            self.total_width = PION_WIDTH
        elif meson_type == "kaon":
            self.mm = M_K
            self.ckm = V_US
            self.fM = F_K
            self.total_width = KAON_WIDTH
        else:
            raise Exception("Meson type not understood!", meson_type)
        self.m_lepton = m_lepton
        self.rep = boson_type
        self.gmu = coupling
        self.EaMax = (self.mm**2 + self.ma**2 - self.m_lepton**2)/(2*self.mm)
        self.EaMin = self.ma
        self.n_samples = n_samples
    
    def lifetime(self, gagamma):
        return 1/W_gg(gagamma, self.ma)

    def dGammadEa(self, Ea):
        m212 = self.mm**2 + self.ma**2 - 2*self.mm*Ea
        e2star = (m212 - self.m_lepton**2)/(2*sqrt(m212))
        e3star = (self.mm**2 - m212 - self.ma**2)/(2*sqrt(m212))

        if self.ma > e3star:
            return 0.0

        m223Max = (e2star + e3star)**2 - (sqrt(e2star**2) - sqrt(e3star**2 - self.ma**2))**2
        m223Min = (e2star + e3star)**2 - (sqrt(e2star**2) + sqrt(e3star**2 - self.ma**2))**2
    
        def MatrixElement2P(m223):
            ev = (m212 + m223 - self.m_lepton**2 - self.ma**2)/(2*self.mm)
            emu = (self.mm**2 - m223 + self.m_lepton**2)/(2*self.mm)
            q2 = self.mm**2 - 2*self.mm*ev

            prefactor = heaviside(e3star-self.ma,0.0)*(self.gmu*G_F*self.fM*self.ckm/(q2 - self.m_lepton**2))**2
            return prefactor*((2*self.mm*emu*q2 * (q2 - self.m_lepton**2) - (q2**2 - (self.m_lepton*self.mm)**2)*(q2 + self.m_lepton**2 - self.ma**2)) - (2*q2*self.m_lepton**2 * (self.mm**2 - q2)))
        
        def MatrixElement2S(m223):
            ev = (m212 + m223 - self.m_lepton**2 - self.ma**2)/(2*self.mm)
            emu = (self.mm**2 - m223 + self.m_lepton**2)/(2*self.mm)
            q2 = self.mm**2 - 2*self.mm*ev

            prefactor = heaviside(e3star-self.ma,0.0)*(self.gmu*G_F*self.fM*self.ckm/(q2 - self.m_lepton**2))**2
            return prefactor*((2*self.mm*emu*q2 * (q2 - self.m_lepton**2) - (q2**2 - (self.m_lepton*self.mm)**2)*(q2 + self.m_lepton**2 - self.ma**2)) + (2*q2*self.m_lepton**2 * (self.mm**2 - q2)))

        def MatrixElement2V(m223):
            q2 = self.mm**2 - 2*self.mm*(m212 + m223 - self.m_lepton**2 - self.ma**2)/(2*self.mm)

            prefactor = heaviside(e3star-self.ma,0.0)*8*power(G_F*self.fM*self.ckm/(q2 - self.m_lepton**2)/self.ma, 2)

            lq = (m212 - self.m_lepton**2)/2
            lp = (self.mm**2 - m212 - m223)/2
            kq = (m212 + m223 - self.m_lepton**2 - self.ma**2)/2
            pq = (m223 - self.ma**2)/2
            kl = (self.mm**2 + self.m_lepton**2 - m223)/2
            kp = (self.mm**2 + self.ma**2 - m212)/2

            cr = self.gmu
            cl = self.gmu

            # Dmu(self.mm/kl)*
            return -prefactor * ((power(cr*self.mm*self.m_lepton,2) - power(cl*q2,2)) * (lq*self.ma**2 + 2*lp*pq) \
                - 2*cr*self.m_lepton**2 * kq * (cr*self.ma**2 * kl + 2*cr*kp*lp - 3*cl*q2*self.ma**2))
        
        def MatrixElement2QV(m223):
            pk = (self.mm**2 + self.ma**2 - m212)/2
            pl = (self.mm**2 + self.m_lepton**2 - m223)/2
            pq = (m212 + m223 - self.m_lepton**2 - self.ma**2)/2
            kl = (self.mm**2 - m212 - m223)/2
            kq = (m223 - self.ma**2)/2
            lq = (m212 - self.m_lepton**2)/2

            # SD piece
            prefactor_SD = 8 * power(self.gmu * G_F * CABIBBO / sqrt(2) / self.mm, 2)
            fv = 1.0 #0.0265
            fa = 1.0 #0.58 * fv

            M_SD = 130 * prefactor_SD * (2 * kl * (power(fa - fv, 2)*pk*pq - self.mm**2 * (fa**2 + fv**2)*kq) \
                    + self.ma**2 * (power(fa*self.mm, 2) * lq - 2*fv**2 * pl * pq) \
                    + 2 * power(fa + fv, 2) * pk * kq * pl)

            # IB piece
            prefactor_IB2 = -16*power(self.gmu * G_F * self.fM * self.mm * self.m_lepton, 2)
            M_IB2 = prefactor_IB2 * ((self.m_lepton**2-m212)*((self.mm**2-m212+self.ma**2)**2 - 4*self.mm**2 * self.ma**2))/(self.ma**2 * (self.mm**2-m212)**2)

            prefactor_IB3 = -2*power(self.gmu * G_F * self.fM * self.m_lepton, 2)
            M_IB3 = -(prefactor_IB3 / self.m_lepton**2) * (8*lq + 16*kl*kq / self.ma**2)

            return M_IB3
        
        if self.rep == "P":
            return (2*self.mm)/(32*power(2*pi*self.mm, 3))*quad(MatrixElement2P, m223Min, m223Max)[0]
        
        if self.rep == "S":
            return (2*self.mm)/(32*power(2*pi*self.mm, 3))*quad(MatrixElement2S, m223Min, m223Max)[0]

        if self.rep == "V":
            return (2*self.mm)/(32*power(2*pi*self.mm, 3))*quad(MatrixElement2V, m223Min, m223Max)[0]
        
        if self.rep == "QV":
            return (2*self.mm)/(32*power(2*pi*self.mm, 3))*quad(MatrixElement2QV, m223Min, m223Max)[0]

    def gamma_sm(self):
        return self.total_width

    def total_br(self):
        EaMax = (self.mm**2 + self.ma**2 - self.m_lepton**2)/(2*self.mm)
        EaMin = self.ma
        return quad(self.dGammadEa, EaMin, EaMax)[0] / self.gamma_sm()
    
    def diff_br(self):
        ea_min = self.ma
        ea_max = (self.mm**2 + self.ma**2 - self.m_lepton**2)/(2*self.mm)
        mc_vol = ea_max - ea_min
        energies = np.random.uniform(ea_min, ea_max, self.n_samples)
        weights = np.array([mc_vol*self.dGammadEa(ea)/self.gamma_sm()/self.n_samples \
            for ea in energies])
        return energies, weights
    
    def simulate_single(self, meson_p, pion_wgt):
        ea_min = self.ma
        ea_max = (self.mm**2 + self.ma**2 - self.m_lepton**2)/(2*self.mm)

        # Draw random variate energies and angles in the pion rest frame
        energies = np.random.uniform(ea_min, ea_max, self.n_samples)
        momenta = sqrt(energies**2 - self.ma**2)
        cosines = np.random.uniform(-1, 1, self.n_samples)
        pz = momenta*cosines

        # Boost to lab frame
        beta = meson_p / sqrt(meson_p**2 + self.mm**2)
        boost = power(1-beta**2, -0.5)
        e_lab = boost*(energies + beta*pz)
        pz_lab = boost*(pz + beta*energies)

        # Jacobian for transforming d2Gamma/(dEa * dOmega) to lab frame:
        jacobian = sqrt(e_lab**2 - self.ma**2) / momenta
        # Monte Carlo volume, making sure to use the lab frame energy range

        mc_vol = ea_max - ea_min
        weights = jacobian*np.array([pion_wgt*mc_vol*self.dGammadEa(ea)/self.gamma_sm()/self.n_samples \
            for ea in energies])

        for i in range(self.n_samples):
            self.axion_energy.append(e_lab[i])
            self.axion_flux.append(weights[i])
    
    def simulate(self, cut_on_solid_angle=True):
        self.axion_energy = []
        self.axion_flux = []
        self.decay_axion_weight = []
        self.scatter_axion_weight = []

        if self.ma > self.mm - self.m_lepton:
            # Kinematically forbidden beyond Meson mass - muon mass difference
            return

        for i, p in enumerate(self.meson_flux):
            # Simulate decays for each charged meson
            self.simulate_single(p[0], p[1])
        

    def propagate(self):  # propagate to detector
        wgt = np.array(self.axion_flux)
        self.decay_axion_weight = np.asarray(wgt*0.0, dtype=np.float64)
        self.scatter_axion_weight = np.asarray(self.det_area / (4*pi*self.det_dist**2) * wgt, dtype=np.float64)





class FluxPi0Isotropic(AxionFlux):
    def __init__(self, pi0_rate=0.0259, boson_mass=0.1, coupling=1.0,
                 boson_type="QV", det_dist=20.0, det_area=2.0, det_length=1.0,
                 target=Material("W"), detector=Material("Ar"), n_samples=1000):
        super().__init__(boson_mass, target, detector, det_dist, det_length, det_area)
        self.meson_rate = pi0_rate
        self.n_samples = n_samples
        self.g = coupling
        self.boson_mass = boson_mass
        self.mm = M_PI0
    
    def br(self):
        return 2 * self.g**2 * (1 - power(self.boson_mass / M_PI0, 2))**3
    
    def simulate_flux(self, pi0_flux, energy_cut=0.0, angle_cut=np.pi):
        # pi0_flux = momenta array, normalized to pi0 rate

        self.axion_energy = []
        self.axion_flux = []
        self.decay_axion_weight = []
        self.scatter_axion_weight = []

        if self.ma > self.mm:
            # Kinematically forbidden
            return

        # Simulate decays for each charged meson
        p_cm = (M_PI0**2 - self.ma**2)/(2*M_PI0)
        e1_cm = sqrt(p_cm**2 + self.ma**2)
        cos_rnd = np.random.uniform(-1, 1, pi0_flux.shape[0])

        for i, p in enumerate(pi0_flux):
            beta = p / sqrt(p**2 + self.mm**2)
            boost = power(1-beta**2, -0.5)
            e_lab = boost*(e1_cm + beta*p_cm*cos_rnd[i])
            pz_lab = boost*(p_cm*cos_rnd[i] + beta*e1_cm)
            angle_lab = arccos(pz_lab / sqrt(e_lab**2 - self.ma**2))
            if e_lab < energy_cut:
                continue
            if angle_lab > angle_cut:
                continue
            self.axion_energy.append(e_lab)
            self.axion_flux.append(self.meson_rate*self.br()/pi0_flux.shape[0])

    
    def simulate(self):
        self.axion_energy = []
        self.axion_flux = []
        self.decay_axion_weight = []
        self.scatter_axion_weight = []

        if self.ma > self.mm:
            # Kinematically forbidden
            return

        # Simulate decays for each charged meson
        p_cm = (M_PI0**2 - self.ma**2)/(2*M_PI0)
        e1_cm = sqrt(p_cm**2 + self.ma**2)

        self.axion_energy.extend(e1_cm*np.ones(self.n_samples))
        self.axion_flux.extend(self.meson_rate * self.br() * np.ones(self.n_samples)/np.sum(self.n_samples))
        

    def propagate(self, is_isotropic=True):
        if is_isotropic:
            wgt = np.array(self.axion_flux)
            self.decay_axion_weight = np.asarray(wgt*0.0, dtype=np.float64)
            self.scatter_axion_weight = np.asarray(self.det_area / (4*pi*self.det_dist**2) * wgt, dtype=np.float64)
        else:
            wgt = np.array(self.axion_flux)
            self.decay_axion_weight = np.asarray(wgt*0.0, dtype=np.float64)
            self.scatter_axion_weight = np.asarray(wgt, dtype=np.float64)




##### DARK MATTER FLUXES #####
rho_chi = 0.4e6 #(* keV / cm^3 *)
vesc = 544.0e6
v0 = 220.0e6
ve = 244.0e6
nesc = erf(vesc/v0) - 2*(vesc/v0) * exp(-(vesc/v0)**2) * sqrt(pi)

def fv(v):  # Velocity profile ( v ~ [0,1] )
    return (1.0 / (nesc * np.power(pi,3/2) * v0**3)) * exp(-((v + ve)**2 / v0**2))

def DMFlux(v, m):  # DM differential flux as a function of v~[0,1] and the DM mass
    return heaviside(v + v0 - vesc) * 4*pi*C_LIGHT*(rho_chi / m) * (C_LIGHT*v)**3 * fv(C_LIGHT*v)


##### NUCLEAR COUPLING FLUXES #####

def Fe57SolarFlux(gp): 
    # Monoenergetic flux at 14.4 keV from the Sun
    return (4.56e23) * gp**2


##### ELECTRON COUPLING FLUXES #####


##### PHOTON COUPLING #####

def PrimakoffSolarFlux(Ea, gagamma):
    # Solar ALP flux
    # input Ea in keV, gagamma in GeV-1
    return (gagamma * 1e8)**2 * (5.95e14 / 1.103) * (Ea / 1.103)**3 / (exp(Ea / 1.103) - 1)



def SunPosition(t):
    pass