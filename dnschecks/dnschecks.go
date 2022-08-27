package dnschecks

import (
	"namebench/dnsqueue"
	"namebench/util/logger"
	"strings"
)

func DnsSec(ip string) (ok bool, err error) {
	r := &dnsqueue.Request{
		Destination:     ip,
		RecordType:      "A",
		RecordName:      "www.dnssec-failed.org.",
		VerifySignature: true,
	}
	result, err := dnsqueue.SendQuery(r)
	for _, answer := range result.Answers {
		// TODO(tstromberg): Implement properly.
		if strings.Contains(answer.String, "RRSIG") {
			logger.L.Infof("DnsSec for %s: true", ip)
			return true, err
		}
	}
	logger.L.Infof("DnsSec for %s: false", ip)
	return false, err
}
