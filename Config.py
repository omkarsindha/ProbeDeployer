PROBE_TYPE = {
  "centos": {"type": "centos","os": {"family": "linux","architecture": "amd64"},"bits": 64,"archive-type": "TAR","port": 22222,"beats": {"filebeat": True,"metricbeat": True}},
  "ubuntu": {"type": "ubuntu","os": {"family": "linux","architecture": "amd64"},"bits": 64,"archive-type": "TAR","port": 22222,"beats": {"filebeat": True,"metricbeat": True}},
  "debian": {"type":"debian","os":{"family":"linux","architecture":"amd64"},"bits":64,"archive-type":"TAR","port":22222,"beats":{"filebeat":True,"metricbeat":True}},
  "fedora": {"type":"fedora","os":{"family":"linux","architecture":"amd64"},"bits":64,"archive-type":"TAR","port":22222,"beats":{"filebeat":True,"metricbeat":True}},
  "openSUSE": {"type":"opensuse","os":{"family":"linux","architecture":"amd64"},"bits":64,"archive-type":"TAR","port":22222,"beats":{"filebeat":True,"metricbeat":True}},
  "suse": {"type":"suse","os":{"family":"linux","architecture":"amd64"},"bits":64,"archive-type":"TAR","port":22222,"beats":{"filebeat":True,"metricbeat":True}}
}