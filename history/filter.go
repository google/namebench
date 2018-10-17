// part of the history package, provides filtering capabilities.
package history

import (
	"golang.org/x/net/publicsuffix"
	"log"
	"math/rand"
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

// Filter out external hostnames from history
func ExternalHostnames(entries []string) (hostnames []string) {
	counter := 0

	for _, uString := range entries {
		u, err := url.ParseRequestURI(uString)
		if err != nil {
			log.Printf("Error parsing %s: %s", uString, err)
			continue
		}
		if !isPossiblyInternal(u.Host) {
			counter += 1
			hostnames = append(hostnames, u.Host)
		}
	}
	return
}

// Filter input array for unique entries.
func Uniq(input []string) (output []string) {
	last := ""
	for _, i := range input {
		if i != last {
			output = append(output, i)
		}
	}
	return
}

// Randomly select X number of entries.
func Random(count int, input []string) (output []string) {
	selected := make(map[int]bool)

	for {
		if len(selected) >= count {
			return
		}
		index := rand.Intn(len(input))
		// If we have already picked this number, re-roll.
		if _, exists := selected[index]; exists == true {
			continue
		}
		output = append(output, input[index])
		selected[index] = true
	}
}
