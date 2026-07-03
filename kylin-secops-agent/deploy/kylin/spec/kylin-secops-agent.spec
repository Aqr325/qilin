# Kylin Security Operations Agent — RPM Spec
# 麒麟安全智能运维Agent — RPM 打包文件
# 适用于 麒麟V10 (KylinOS V10) / 银河麒麟高级服务器操作系统 V10
#
# 构建:
#   sudo dnf install -y rpm-build python3-devel
#   rpmbuild -bb kylin-secops-agent.spec

%define agent_name kylin-secops-agent
%define agent_version 3.2.0
%define agent_release 1.kylinv10

Name:       %{agent_name}
Version:    %{agent_version}
Release:    %{agent_release}
Summary:    Kylin Security Operations Agent - Intelligent Security Monitoring for KylinOS

Group:      System Environment/Daemons
License:    Proprietary
URL:        https://secops.company.com
Source0:    %{agent_name}-%{version}.tar.gz
BuildArch:  x86_64

# 构建依赖
BuildRequires:  python3-devel >= 3.11
BuildRequires:  python3-pip
BuildRequires:  systemd-rpm-macros

# 运行时依赖
Requires:       python3 >= 3.11
Requires:       python3-psutil
Requires:       systemd
Requires(pre):  shadow-utils

%description
Kylin Security Operations Agent provides intelligent security monitoring
for KylinOS systems. Features include:
- Real-time system resource monitoring (CPU, memory, disk, network)
- Security event collection (process, file, log, network)
- MITRE ATT&CK mapped alerting engine
- Offline-capable operation with local SQLite buffer
- Secure WebSocket communication with backend platform
- OTA upgrade with signature verification

中文描述：
麒麟安全智能运维Agent，为麒麟操作系统提供智能安全监控能力。
- 实时系统资源监控（CPU、内存、磁盘、网络）
- 安全事件采集（进程、文件、日志、网络）
- MITRE ATT&CK 映射告警引擎
- 离线模式运行，本地 SQLite 缓冲
- WebSocket 加密通信
- OTA 升级与签名验证

%prep
%setup -q -n %{agent_name}-%{version}

%build
# Python 包无需编译
# 创建虚拟环境用于 pip 安装依赖
%{__python3} -m venv %{_builddir}/venv
source %{_builddir}/venv/bin/activate
pip install --no-cache-dir -r requirements.txt

%install
# 创建目录结构
install -d %{buildroot}%{_datadir}/%{agent_name}
install -d %{buildroot}%{_sysconfdir}/%{agent_name}
install -d %{buildroot}%{_localstatedir}/lib/%{agent_name}
install -d %{buildroot}%{_localstatedir}/log/%{agent_name}
install -d %{buildroot}%{_localstatedir}/run/%{agent_name}
install -d %{buildroot}%{_unitdir}

# 复制 Python 源码
cp -a src/ %{buildroot}%{_datadir}/%{agent_name}/

# 安装 systemd 服务
install -m 644 systemd/%{agent_name}.service %{buildroot}%{_unitdir}/

# 安装默认配置
install -m 640 src/config.py %{buildroot}%{_sysconfdir}/%{agent_name}/config.yaml.example

# 创建 wrapper 脚本
cat > %{buildroot}%{_bindir}/%{agent_name} << 'WRAPPER'
#!/usr/bin/env python3
import sys
sys.path.insert(0, "%{_datadir}/%{agent_name}")
from src.main import main
main()
WRAPPER
chmod 755 %{buildroot}%{_bindir}/%{agent_name}

%pre
# 创建服务用户
getent group %{agent_name} >/dev/null || groupadd -r %{agent_name}
getent passwd %{agent_name} >/dev/null || \
    useradd -r -g %{agent_name} -d %{_localstatedir}/lib/%{agent_name} \
    -s /sbin/nologin -c "Kylin SecOps Agent" %{agent_name}

%post
# 设置权限
chown -R %{agent_name}:%{agent_name} %{_localstatedir}/lib/%{agent_name}
chown -R %{agent_name}:%{agent_name} %{_localstatedir}/log/%{agent_name}
chown -R %{agent_name}:%{agent_name} %{_localstatedir}/run/%{agent_name}

# 创建默认配置（如果不存在）
if [[ ! -f %{_sysconfdir}/%{agent_name}/config.yaml ]]; then
    cp %{_sysconfdir}/%{agent_name}/config.yaml.example \
       %{_sysconfdir}/%{agent_name}/config.yaml
    chmod 640 %{_sysconfdir}/%{agent_name}/config.yaml
    chown %{agent_name}:%{agent_name} %{_sysconfdir}/%{agent_name}/config.yaml
fi

# 重载 systemd
%{_bindir}/systemctl daemon-reload

%preun
# 停止服务
%{_bindir}/systemctl stop %{agent_name}.service 2>/dev/null || true

%postun
# 卸载后清理
if [[ $1 -eq 0 ]]; then
    %{_bindir}/systemctl daemon-reload
    %{_bindir}/systemctl reset-failed 2>/dev/null || true

    # 询问是否删除数据
    echo "Remove configuration? (y/N): "
    read -r answer
    if [[ "$answer" == [yY] ]]; then
        rm -rf %{_sysconfdir}/%{agent_name}
    fi

    echo "Remove data? (y/N): "
    read -r answer
    if [[ "$answer" == [yY] ]]; then
        rm -rf %{_localstatedir}/lib/%{agent_name}
    fi
fi

%files
%defattr(-,root,root,-)
%{_bindir}/%{agent_name}
%{_datadir}/%{agent_name}/
%{_unitdir}/%{agent_name}.service

%config(noreplace)
%attr(640,%{agent_name},%{agent_name}) %{_sysconfdir}/%{agent_name}/config.yaml.example

%dir %attr(750,%{agent_name},%{agent_name}) %{_localstatedir}/lib/%{agent_name}
%dir %attr(750,%{agent_name},%{agent_name}) %{_localstatedir}/log/%{agent_name}
%dir %attr(750,%{agent_name},%{agent_name}) %{_localstatedir}/run/%{agent_name}

%changelog
* Tue Jun 21 2026 Kylin SecOps Team <dev@secops.company.com> - 3.2.0-1
- Initial KylinOS V10 release
- Real-time system monitoring
- Security event collection
- MITRE ATT&CK engine
- Offline-capable operation
- OTA upgrade support
- Kylin UKUI desktop integration
- Kylin security module (kysec) support
