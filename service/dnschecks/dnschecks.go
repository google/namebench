package dnschecks

import (
	"fmt"
	"github.com/Cellularhacker/logger-go"
	"namebench/model/namebench/record"
	"namebench/service/dnsqueue"
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
	IsISP     bool   `json:"is_isp"`
}

func (ds *DnsServer) Address() string {
	return fmt.Sprintf("%s:%d", string(ds.IP), ds.Port)
}

func (ds *DnsServer) GetName() string {
	pStr := Primary
	if !ds.IsPrimary {
		pStr = Secondary
	}
	if ds.IsISP {
		pStr += ", ISP"
	}

	return fmt.Sprintf("%s(%s)", ds.Name, pStr)
}

type CheckResult struct {
	DnsServer *DnsServer     `json:"dns_server"`
	Timer     *Timer         `json:"timer"`
	DnsSec    bool           `json:"dns_sec"`
	Record    *record.Record `json:"record,omitempty"`
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

	addrStr := fmt.Sprintf("Address: %s,", cr.DnsServer.Address())
	if len(addrStr) < 24 && joinStr == "\t" {
		if len(addrStr) < 16 {
			addrStr += "\t"
		}
		addrStr += "\t"
	}
	tookStr := fmt.Sprintf("Took: %s", cr.Timer.Took.String())
	if len(tookStr) < 16 && joinStr == "\t" {
		if len(tookStr) < 8 {
			tookStr += "\t"
		}
		tookStr += "\t"
	}

	strs := []string{
		addrStr,
		fmt.Sprintf("DNSSEC: %s,", cr.DNSSEC()),
		tookStr,
		fmt.Sprintf("- %s", cr.DnsServer.GetName()),
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

		crStr := fmt.Sprintf("[%02d/%d] %s", i+1, len(*crs), cr.StringWith(joinStr))
		strs = append(strs, crStr)
	}

	return strings.Join(strs, "\n")
}

func NewDnsServerWithValue(ip string, port int, name string, isPrimary bool, isISP bool) *DnsServer {
	return &DnsServer{
		IP:        []byte(ip),
		Port:      port,
		Name:      name,
		IsPrimary: isPrimary,
		IsISP:     isISP,
	}
}

var DnsServers = []*DnsServer{
	NewDnsServerWithValue("8.8.8.8", 53, "Google Public DNS", true, false),
	NewDnsServerWithValue("8.8.4.4", 53, "Google Public DNS", false, false),
	NewDnsServerWithValue("75.75.75.75", 53, "Comcast DNS", true, true),
	NewDnsServerWithValue("4.2.2.1", 53, "Raytheon BBN DNS", true, false),
	NewDnsServerWithValue("208.67.222.222", 53, "Cisco OpenDNS", true, false),
	NewDnsServerWithValue("208.67.222.220", 53, "Cisco OpenDNS", false, false),
	NewDnsServerWithValue("168.126.63.1:53", 53, "KT", true, true),
	NewDnsServerWithValue("168.126.63.2:53", 53, "KT", false, true),
	NewDnsServerWithValue("210.220.163.82", 53, "SK Broadband", true, true),
	NewDnsServerWithValue("219.250.36.130", 53, "SK Broadband", false, true),
	NewDnsServerWithValue("61.41.153.2", 53, "LG DACOM", true, true),
	NewDnsServerWithValue("1.214.68.2", 53, "LG DACOM", false, true),
	NewDnsServerWithValue("164.124.101.2", 53, "LG DACOM(ex-LG Powercomm)", true, true),
	NewDnsServerWithValue("203.248.252.2", 53, "LG DACOM(ex-LG Powercomm)", false, true),
	NewDnsServerWithValue("180.182.54.1", 53, "LG HelloVision Corp.", true, true),
	NewDnsServerWithValue("180.182.54.2", 53, "LG HelloVision Corp.", false, true),
	NewDnsServerWithValue("9.9.9.9", 53, "IBM Quad9", true, false),
	NewDnsServerWithValue("149.112.112.112", 53, "IBM Quad9", false, false),
	NewDnsServerWithValue("194.242.2.2", 53, "Mullvad VPN", true, false),
	NewDnsServerWithValue("193.19.108.2", 53, "Mullvad VPN", false, false),
	NewDnsServerWithValue("185.222.222.222", 53, "DNS.SB", true, false),
	NewDnsServerWithValue("45.11.45.11", 53, "DNS.SB", false, false),
	NewDnsServerWithValue("182.172.225.180", 53, "DLive", true, true),
	NewDnsServerWithValue("203.246.162.253", 53, "DLive", false, true),
	NewDnsServerWithValue("1.1.1.1", 53, "Cloudflare DNS", true, false),
	NewDnsServerWithValue("1.0.0.1", 53, "Cloudflare DNS", false, false),
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

func DnsSec(ds *DnsServer, records ...*record.Record) (*CheckResult, error) {
	t := NewTimer()

	rec := record.Default
	if len(records) > 0 {
		rec = records[0]
	}

	r := &dnsqueue.Request{
		Destination:     ds.Address(),
		RecordType:      rec.Type,
		RecordName:      rec.Name,
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
