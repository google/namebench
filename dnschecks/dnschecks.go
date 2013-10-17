package dnschecks

import (
	"github.com/google/namebench/dnsqueue"
	"log"
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
			log.Printf("DnsSec for %s: true", ip)
			return true, err
		}
	}
	log.Printf("DnsSec for %s: false", ip)
	return false, err
}
