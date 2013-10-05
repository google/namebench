// part of the history package, provides filtering capabilities.
package history

import (
	"code.google.com/p/go.net/publicsuffix"
	"log"
	"net/url"
	"regexp"
)

var (
	internal_re = regexp.MustCompile(`\.corp|\.sandbox\.|\.borg\.|\.hot\.|internal|dmz|\._[ut][dc]p\.|intra|\.\w$|\.\w{5,}$`)
)

func isPossiblyInternal(addr string) bool {
	// note: this happens to reject IPs and anything with a port at the end.
	_, icann := publicsuffix.PublicSuffix(addr)
	if !icann {
		log.Printf("%s does not have a public suffix", addr)
		return true
	}
	if internal_re.MatchString(addr) {
		log.Printf("%s may be internal.", addr)
		return true
	}
	return false
}

func ExternalHostnames(entries []string) (hostnames []string) {
	for _, uString := range entries {
		u, err := url.ParseRequestURI(uString)
		if err != nil {
			log.Printf("Error parsing %s: %s", uString, err)
			continue
		}
		if !isPossiblyInternal(u.Host) {
			hostnames = append(hostnames, u.Host)
		}
	}
	return
}
