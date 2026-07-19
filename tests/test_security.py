import pytest

from crawler.security import SSRFBlockedError, SSRFGuard


async def test_blocks_loopback_ip():
    guard = SSRFGuard()
    with pytest.raises(SSRFBlockedError):
        await guard.check("http://127.0.0.1/")


async def test_blocks_private_network_ip():
    guard = SSRFGuard()
    with pytest.raises(SSRFBlockedError):
        await guard.check("http://10.0.0.5/")


async def test_blocks_cloud_metadata_ip():
    guard = SSRFGuard()
    with pytest.raises(SSRFBlockedError):
        await guard.check("http://169.254.169.254/latest/meta-data/")


async def test_blocks_localhost_hostname_by_default():
    guard = SSRFGuard()
    with pytest.raises(SSRFBlockedError):
        await guard.check("http://localhost/")


async def test_blocks_file_scheme_by_default():
    guard = SSRFGuard()
    with pytest.raises(SSRFBlockedError):
        await guard.check("file:///etc/passwd")


async def test_blocks_unsupported_scheme():
    guard = SSRFGuard()
    with pytest.raises(SSRFBlockedError):
        await guard.check("ftp://example.com/file")


async def test_allows_public_ip():
    guard = SSRFGuard()
    await guard.check("http://8.8.8.8/")  # should not raise


async def test_allow_localhost_flag_permits_it():
    guard = SSRFGuard(allow_localhost=True)
    await guard.check("http://127.0.0.1/")  # should not raise
