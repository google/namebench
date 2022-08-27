package dnschecks

import (
	"fmt"
	"namebench/dnsqueue"
	"namebench/util/logger"
	"net"
	"sort"
	"strings"
	"time"
)

const (
	Primary   = "Primary"
	Secondary = "Secondary"
)

type DnsServer struct {
	IP        net.IP `json:"ip"`
	Port      int    `json:"port"`
	Name      string `json:"name"`
	IsPrimary bool   `json:"is_primary"`
}

func (ds *DnsServer) Address() string {
	return fmt.Sprintf("%s:%d", string(ds.IP), ds.Port)
}

func (ds *DnsServer) GetName() string {
	pStr := Primary
	if !ds.IsPrimary {
		pStr = Secondary
	}

	return fmt.Sprintf("%s(%s)", ds.Name, pStr)
}

type CheckResult struct {
	DnsServer *DnsServer `json:"dns_server"`
	Timer     *Timer     `json:"timer"`
	DnsSec    bool       `json:"dns_sec"`
}

func (cr *CheckResult) DNSSEC() string {
	if cr.DnsSec {
		return "O"
	}
	return "X"
}

func (cr *CheckResult) String() string {
	return cr.StringWith(" ")
}

func (cr *CheckResult) StringWith(joinStr string) string {
	if cr.DnsServer == nil || cr.Timer == nil {
		return ""
	}

	strs := []string{
		fmt.Sprintf("Address: %s,", cr.DnsServer.Address()),
		fmt.Sprintf("DNSSEC: %s,", cr.DNSSEC()),
		fmt.Sprintf("Took: %s", cr.Timer.Took.String()),
		"-",
		fmt.Sprintf("%s", cr.DnsServer.GetName()),
	}

	return strings.Join(strs, joinStr)
}

type CheckResults []CheckResult

func (crs *CheckResults) Sort() {
	if crs == nil {
		return
	}

	sort.Slice(*crs, func(i, j int) bool {
		return (*crs)[i].Timer.Took < (*crs)[j].Timer.Took
	})
}

func (crs *CheckResults) String() string {
	return crs.StringWith(" ")
}

func (crs *CheckResults) StringWith(joinStr string) string {
	if crs == nil {
		return ""
	}
	strs := make([]string, 0)

	for i := range *crs {
		cr := (*crs)[i]

		crStr := fmt.Sprintf("[%d/%d] %s", i+1, len(*crs), cr.StringWith(joinStr))
		strs = append(strs, crStr)
	}

	return strings.Join(strs, "\n")
}

func NewDnsServerWithValue(ip string, port int, name string, isPrimary bool) *DnsServer {
	return &DnsServer{
		IP:        []byte(ip),
		Port:      port,
		Name:      name,
		IsPrimary: isPrimary,
	}
}

var DnsServers = []*DnsServer{
	NewDnsServerWithValue("8.8.8.8", 53, "Google Public DNS", true),
	NewDnsServerWithValue("8.8.4.4", 53, "Google Public DNS", false),
	NewDnsServerWithValue("75.75.75.75", 53, "Comcast DNS", true),
	NewDnsServerWithValue("4.2.2.1", 53, "Raytheon BBN DNS", true),
	NewDnsServerWithValue("208.67.222.222", 53, "Cisco OpenDNS", true),
	NewDnsServerWithValue("208.67.222.220", 53, "Cisco OpenDNS", false),
	NewDnsServerWithValue("168.126.63.1:53", 53, "KT", true),
	NewDnsServerWithValue("168.126.63.2:53", 53, "KT", false),
	NewDnsServerWithValue("210.220.163.82", 53, "SK Broadband", true),
	NewDnsServerWithValue("219.250.36.130", 53, "SK Broadband", false),
	NewDnsServerWithValue("61.41.153.2", 53, "LG DACOM", true),
	NewDnsServerWithValue("1.214.68.2", 53, "LG DACOM", false),
	NewDnsServerWithValue("164.124.101.2", 53, "LG DACOM(ex-LG Powercomm)", true),
	NewDnsServerWithValue("203.248.252.2", 53, "LG DACOM(ex-LG Powercomm)", false),
	NewDnsServerWithValue("180.182.54.1", 53, "LG HelloVision Corp.", true),
	NewDnsServerWithValue("180.182.54.2", 53, "LG HelloVision Corp.", false),
	NewDnsServerWithValue("9.9.9.9", 53, "IBM Quad9", true),
	NewDnsServerWithValue("149.112.112.112", 53, "IBM Quad9", false),
	NewDnsServerWithValue("194.242.2.2", 53, "Mullvad VPN", true),
	NewDnsServerWithValue("193.19.108.2", 53, "Mullvad VPN", false),
	NewDnsServerWithValue("185.222.222.222", 53, "DNS.SB", true),
	NewDnsServerWithValue("45.11.45.11", 53, "DNS.SB", false),
	NewDnsServerWithValue("182.172.225.180", 53, "DLive", true),
	NewDnsServerWithValue("203.246.162.253", 53, "DLive", false),
}

type Timer struct {
	StartedAt time.Time     `json:"started_at,omitempty"`
	EndedAt   time.Time     `json:"ended_at,omitempty"`
	Took      time.Duration `json:"took,omitempty"`
}

func (t *Timer) Stop() {
	t.EndedAt = time.Now()
}

func (t *Timer) StopAndReturn() *Timer {
	if t.EndedAt.IsZero() {
		t.Stop()
	}
	t.Took = t.EndedAt.Sub(t.StartedAt)

	return t
}

func (t *Timer) StopAndReturnToResult(ds *DnsServer, dnsSec bool) *CheckResult {
	t.StopAndReturn()

	return &CheckResult{
		DnsServer: ds,
		Timer:     t,
		DnsSec:    dnsSec,
	}
}

func NewTimer() *Timer {
	return &Timer{
		StartedAt: time.Now(),
	}
}

func DnsSec(ds *DnsServer) (*CheckResult, error) {
	t := NewTimer()

	r := &dnsqueue.Request{
		Destination:     ds.Address(),
		RecordType:      "A",
		RecordName:      "www.dnssec-failed.org.",
		VerifySignature: true,
	}
	result, err := dnsqueue.SendQuery(r)
	for _, answer := range result.Answers {
		// TODO(tstromberg): Implement properly.
		if strings.Contains(answer.String, "RRSIG") {
			logger.L.Debugf("DnsSec for %s: true", ds.Address())
			return t.StopAndReturnToResult(ds, true), err
		}
	}
	logger.L.Debugf("DnsSec for %s: false", ds.Address())
	return t.StopAndReturnToResult(ds, false), err
}
