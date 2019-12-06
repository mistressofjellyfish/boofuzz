from __future__ import absolute_import
import errno
import socket
import ssl

from future.utils import raise_
from . import exception, helpers, ip_constants, tcp_socket_connection


class SSLSocketConnection(tcp_socket_connection.TCPSocketConnection):
    """BaseSocketConnection implementation for use with SSL Sockets.

    Args:
        host (str): Hostname or IP adress of target system.
        port (int): Port of target service.
        send_timeout (float): Seconds to wait for send before timing out. Default 5.0.
        recv_timeout (float): Seconds to wait for recv before timing out. Default 5.0.
        server (bool): Set to True to enable server side fuzzing.
        sslcontext (ssl.SSLContext): Python SSL context to be used. Required if server=True or server_hostname=None.
        server_hostname (string): server_hostname, required for verifying identity of remote SSL/TLS server
    """

    def __init__(
        self, host, port, send_timeout=5.0, recv_timeout=5.0, server=False, sslcontext=None, server_hostname=None
    ):
        super().__init__(host, port, send_timeout, recv_timeout, server)

        if self.server is True and self.sslcontext is None:
            raise ValueError("Parameter sslcontext is required when server=True.")
        if self.sslcontext is None and self.server_hostname is None:
            raise ValueError("SSL/TLS requires either sslcontext or server_hostname to be set.")

    def open(self):
        super().open()

        # If boofuzz is the SSL client and user did not give us a SSLContext,
        # then we just use a default one.
        if self.server is False and self.sslcontext is None:
            self.sslcontext = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
            self.sslcontext.check_hostname = True
            self.sslcontext.verify_flags = ssl.CERT_REQUIRED

        try:
            self._sock = self.sslcontext.wrap_socket(
                self._sock, server_side=self.server, server_hostname=self.server_hostname
            )
        except ssl.SSLError as e:
            raise exception.BoofuzzTargetConnectionFailedError(str(e))

    def recv(self, max_bytes):
        """
        Receive up to max_bytes data from the target.

        Args:
            max_bytes (int): Maximum number of bytes to receive.

        Returns:
            Received data.
        """
        try:
            super().recv(max_bytes)
        except ssl.SSLError as e:
            # If an SSL error is thrown the connection should be treated as lost
            raise_(exception.BooFuzzSSLError(e.reason))
        # all other exceptions should be handled / raised / re-raised by the parent class

    def send(self, data):
        """
        Send data to the target. Only valid after calling open!

        Args:
            data: Data to send.

        Returns:
            int: Number of bytes actually sent.
        """

        num_bytes = 0

        if len(data) > 0:
            try:
                num_bytes = super().send(data)
            except ssl.SSLError as e:
                # If an SSL error is thrown the connection should be treated as lost.
                # All other exceptions should be handled / raised / re-raised by the parent class.
                raise_(exception.BoofuzzSSLError(e.reason))
