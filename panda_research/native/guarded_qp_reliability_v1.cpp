// Thin C ABI for ProxQP 0.7.2, with its mathematical settings unchanged.
// The build script applies the separately recorded support-function sign fix.
#include <proxsuite/proxqp/dense/dense.hpp>
#include <limits>
#include <exception>

extern "C" int panda_qp_solve(int m, const double* target,
                             const double* matrix, const double* upper,
                             double* x, double* z, double* info) {
  try {
    using namespace proxsuite::proxqp;
    dense::QP<double> qp(7, 0, m);
    qp.settings.eps_abs = 1e-12;
    qp.settings.eps_rel = 0.;
    qp.settings.max_iter = 10000;
    qp.settings.check_duality_gap = true;
    qp.settings.eps_duality_gap_abs = 1e-12;
    qp.settings.eps_duality_gap_rel = 0.;
    Eigen::MatrixXd H = Eigen::MatrixXd::Identity(7,7);
    Eigen::VectorXd g = -Eigen::Map<const Eigen::VectorXd>(target,7);
    Eigen::MatrixXd C = Eigen::Map<const Eigen::Matrix<double,Eigen::Dynamic,Eigen::Dynamic,Eigen::RowMajor>>(matrix,m,7);
    Eigen::VectorXd u = Eigen::Map<const Eigen::VectorXd>(upper,m);
    Eigen::VectorXd l = Eigen::VectorXd::Constant(m,-std::numeric_limits<double>::infinity());
    qp.init(H,g,proxsuite::nullopt,proxsuite::nullopt,C,l,u);
    qp.solve();
    Eigen::Map<Eigen::VectorXd>(x,7) = qp.results.x;
    Eigen::Map<Eigen::VectorXd>(z,m) = qp.results.z;
    info[0] = static_cast<int>(qp.results.info.status);
    info[1] = qp.results.info.iter;
    info[2] = qp.results.info.duality_gap;
    info[3] = qp.results.info.pri_res;
    info[4] = qp.results.info.dua_res;
    return 0;
  } catch (const std::exception&) { return -1; }
}
