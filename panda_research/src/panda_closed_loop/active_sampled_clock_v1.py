"""Match actual shared RK4 endpoints; never interpolate refinement metrics."""
import numpy as np

def common_energy_indices(tx,ty):
    tx=np.asarray(tx);ty=np.asarray(ty)
    if len(tx)<2 or len(ty)<2:raise ValueError('Need two regular endpoint clocks')
    hx=float(np.median(np.diff(np.r_[0.,tx])));hy=float(np.median(np.diff(np.r_[0.,ty])))
    if hx<=0 or hy<=0:raise ValueError('Invalid clock')
    if not np.allclose(tx,np.arange(1,len(tx)+1)*hx,rtol=0,atol=1e-12):raise ValueError('Irregular first clock')
    if not np.allclose(ty,np.arange(1,len(ty)+1)*hy,rtol=0,atol=1e-12):raise ValueError('Irregular second clock')
    if abs(tx[-1]-ty[-1])>1e-12:raise ValueError('Different horizons')
    common=max(hx,hy);sx=round(common/hx);sy=round(common/hy)
    if abs(sx*hx-common)>1e-12 or abs(sy*hy-common)>1e-12:raise ValueError('Clocks not nested')
    ix=np.arange(sx-1,len(tx),sx);iy=np.arange(sy-1,len(ty),sy)
    if len(ix)!=len(iy) or not np.allclose(tx[ix],ty[iy],rtol=0,atol=1e-12):raise ValueError('No exact shared clock')
    return ix,iy
