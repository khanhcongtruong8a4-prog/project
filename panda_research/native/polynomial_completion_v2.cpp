// General-dimensional completion QP. Uses the separately built, sign-corrected
// ProxQP 0.7.2 headers. H=I; all returned candidates require Python KKT audit.
#include <proxsuite/proxqp/dense/dense.hpp>
#include <limits>
extern "C" int panda_completion(int n,int m,const double* target,const double* matrix,const double* upper,double* x,double* z,double* info) {
 try {
  using namespace proxsuite::proxqp;
  dense::QP<double> qp(n,0,m);
  qp.settings.eps_abs=1e-12; qp.settings.eps_rel=0.; qp.settings.max_iter=10000;
  qp.settings.check_duality_gap=true;qp.settings.eps_duality_gap_abs=1e-12;qp.settings.eps_duality_gap_rel=0.;
  Eigen::MatrixXd H=Eigen::MatrixXd::Identity(n,n);
  Eigen::VectorXd g=-Eigen::Map<const Eigen::VectorXd>(target,n);
  Eigen::MatrixXd C=Eigen::Map<const Eigen::Matrix<double,Eigen::Dynamic,Eigen::Dynamic,Eigen::RowMajor>>(matrix,m,n);
  Eigen::VectorXd b=Eigen::Map<const Eigen::VectorXd>(upper,m);
  qp.init(H,g,proxsuite::nullopt,proxsuite::nullopt,C,Eigen::VectorXd::Constant(m,-std::numeric_limits<double>::infinity()),b);
  qp.solve();Eigen::Map<Eigen::VectorXd>(x,n)=qp.results.x;Eigen::Map<Eigen::VectorXd>(z,m)=qp.results.z;
  info[0]=static_cast<int>(qp.results.info.status);info[1]=qp.results.info.iter;info[2]=qp.results.info.duality_gap;
  return 0;
 } catch(...) {return -1;}
}
