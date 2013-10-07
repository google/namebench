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

// Filter out external hostnames from history, with a limit of X records (may be 0).
func ExternalHostnames(entries []string, limit int) (hostnames []string) {
	counter := 0

	for _, uString := range entries {
		u, err := url.ParseRequestURI(uString)
		if err != nil {
			log.Printf("Error parsing %s: %s", uString, err)
			continue
		}
		if !isPossiblyInternal(u.Host) {
			counter += 1
			if limit > 0 && counter > limit {
				return
			}
			hostnames = append(hostnames, u.Host)
		}
	}
	return
}
