%global forgeurl https://github.com/SakibShahariar/rpmdrop

Name:           rpmdrop
Version:        0.1.0
Release:        1%{?dist}
Summary:        Native GNOME application for inspecting local RPM packages
License:        GPL-3.0-or-later
URL:            %{forgeurl}
Source0:        %{forgeurl}/archive/refs/tags/v%{version}.tar.gz

BuildArch:      noarch
BuildRequires:  python3-devel
BuildRequires:  python3-setuptools
BuildRequires:  pyproject-rpm-macros
BuildRequires:  desktop-file-utils

Requires:       gtk4
Requires:       libadwaita
Requires:       python3-gobject
Requires:       python3-dbus
Requires:       rpm
Requires:       dnf5daemon-server
Recommends:     rpmdrop-nautilus

%description
RpmDrop is a lightweight GTK 4 and libadwaita application for inspecting
local RPM packages and previewing DNF5 dependency transactions before
installation.

%package nautilus
Summary:        Optional GNOME Files context-menu action for RpmDrop
Requires:       %{name} = %{version}-%{release}
Requires:       nautilus-python

%description nautilus
Adds an optional "Inspect with RpmDrop" context-menu action to GNOME Files.
It passes selected local RPM files to RpmDrop and never starts installation
directly from the context menu.

%prep
%autosetup -n %{name}-%{version}

%generate_buildrequires
%pyproject_buildrequires

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files rpmdrop
install -Dpm0644 data/nautilus-rpmdrop.py \
    %{buildroot}%{_datadir}/nautilus-python/extensions/nautilus-rpmdrop.py

%check
desktop-file-validate %{buildroot}%{_datadir}/applications/io.github.sakibshahariar.RpmDrop.desktop

%files -f %{pyproject_files}
%{_bindir}/rpmdrop
%doc README.md
%{_datadir}/applications/io.github.sakibshahariar.RpmDrop.desktop

%files nautilus
%{_datadir}/nautilus-python/extensions/nautilus-rpmdrop.py
%exclude %{_datadir}/nautilus-python/extensions/__pycache__/*

%changelog
* Mon Nov 16 2026 Sakib Shahariar Shimanto <sakibshahariar@users.noreply.github.com> - 0.1.0-1
- Initial Fedora package.
