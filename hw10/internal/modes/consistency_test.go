package modes_test

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"strconv"
	"testing"
	"time"

	"distributed-kv/internal/api"
	"distributed-kv/internal/cluster"
	"distributed-kv/internal/config"
	"distributed-kv/internal/modes"
	"distributed-kv/internal/store"
)

type cluster5 struct{ urls []string }
type resp struct {
	Key     string `json:"key"`
	Value   string `json:"value"`
	Version int64  `json:"version"`
	NodeID  string `json:"node_id"`
}

func TestLeaderReadLeaderAfterAck(t *testing.T) {
	c := start(t, "leader-follower", 1, 5)
	client := &http.Client{Timeout: 5 * time.Second}
	leader := c.urls[0]

	key, value := "k1", "v1"
	status, _ := put(t, client, leader, key, value)
	if status != 201 {
		t.Fatalf("leader PUT expected 201, got %d", status)
	}

	status, body := get(t, client, leader, "/kv/", key)
	fmt.Printf("Leader GET after ack -> status=%d body=%+v\n", status, body)

	if status != 200 || body.Value != value {
		t.Fatalf("leader read inconsistent: status=%d body=%+v", status, body)
	}
}

func TestLeaderReadFollowerAfterAck(t *testing.T) {
	c := start(t, "leader-follower", 1, 5)
	client := &http.Client{Timeout: 5 * time.Second}
	leader, follower := c.urls[0], c.urls[4]

	key, value := "k2", "v2"
	status, _ := put(t, client, leader, key, value)
	if status != 201 {
		t.Fatalf("leader PUT expected 201, got %d", status)
	}

	status, body := get(t, client, follower, "/kv/", key)
	fmt.Printf("Follower GET after leader ack -> status=%d body=%+v\n", status, body)

	if status != 200 || body.Value != value {
		t.Fatalf("follower read inconsistent: status=%d body=%+v", status, body)
	}
}

func TestInconsistencyWindows(t *testing.T) {
	// -------- Leader database: local_read during set --------
	lf := start(t, "leader-follower", 1, 5)
	client := &http.Client{Timeout: 5 * time.Second}
	leader := lf.urls[0]

	done1 := make(chan struct{})
	go func() {
		_, _ = put(t, client, leader, "leader-window", "value")
		close(done1)
	}()

	time.Sleep(50 * time.Millisecond)
	fmt.Println("Leader-Follower: local_read during set")
	for i := 1; i < 5; i++ {
		s, raw := rawGet(t, client, lf.urls[i], "/local_read/", "leader-window")
		fmt.Printf("follower%d local_read -> status=%d body=%s\n", i+1, s, raw)
	}
	<-done1

	// -------- Leaderless database: GET during write + consistency after ack --------
	ll := start(t, "leaderless", 1, 5)
	coord, other := ll.urls[1], ll.urls[4]

	done2 := make(chan struct{})
	go func() {
		_, _ = put(t, client, coord, "leaderless-window", "value")
		close(done2)
	}()

	time.Sleep(50 * time.Millisecond)
	fmt.Println("Leaderless: GET during write")
	for i := 0; i < 5; i++ {
		if ll.urls[i] == coord {
			continue
		}
		s, raw := rawGet(t, client, ll.urls[i], "/kv/", "leaderless-window")
		fmt.Printf("node%d GET -> status=%d body=%s\n", i+1, s, raw)
	}
	<-done2

	s1, b1 := get(t, client, coord, "/kv/", "leaderless-window")
	fmt.Printf("Coordinator GET after ack -> status=%d body=%+v\n", s1, b1)
	if s1 != 200 || b1.Value != "value" {
		t.Fatalf("coordinator inconsistent after ack: status=%d body=%+v", s1, b1)
	}

	s2, b2 := get(t, client, other, "/kv/", "leaderless-window")
	fmt.Printf("Other node GET after ack -> status=%d body=%+v\n", s2, b2)
	if s2 != 200 || b2.Value != "value" {
		t.Fatalf("other node inconsistent after ack: status=%d body=%+v", s2, b2)
	}
}

func start(t *testing.T, mode string, r, w int) *cluster5 {
	t.Helper()
	ls, urls, svrs := make([]net.Listener, 5), make([]string, 5), make([]*http.Server, 0, 5)

	for i := 0; i < 5; i++ {
		ln, err := net.Listen("tcp", "127.0.0.1:0")
		if err != nil {
			t.Fatal(err)
		}
		ls[i], urls[i] = ln, "http://"+ln.Addr().String()
	}

	for i := 0; i < 5; i++ {
		cfg := config.Config{
			NodeID:    fmt.Sprintf("node%d", i+1),
			Port:      strconv.Itoa(ls[i].Addr().(*net.TCPAddr).Port),
			Mode:      mode,
			IsLeader:  mode == "leader-follower" && i == 0,
			SelfURL:   urls[i],
			LeaderURL: urls[0],
			N:         5,
			R:         r,
			W:         w,
			Nodes:     append([]string(nil), urls...),
		}
		st := store.NewMemoryStore()
		cc := cluster.NewHTTPClient(3 * time.Second)
		var svc modes.Service
		if mode == "leader-follower" {
			svc = modes.NewLeaderFollowerService(cfg, st, cc)
		} else {
			svc = modes.NewLeaderlessService(cfg, st, cc)
		}
		srv := &http.Server{Handler: api.NewServer(svc, cfg.NodeID).Routes()}
		svrs = append(svrs, srv)
		go srv.Serve(ls[i])
	}

	t.Cleanup(func() {
		ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
		defer cancel()
		for _, s := range svrs {
			_ = s.Shutdown(ctx)
		}
	})

	wait(urls)
	return &cluster5{urls: urls}
}

func wait(urls []string) {
	client := &http.Client{Timeout: 300 * time.Millisecond}
	for _, u := range urls {
		for i := 0; i < 50; i++ {
			resp, err := client.Get(u + "/health")
			if err == nil && resp.StatusCode == 200 {
				resp.Body.Close()
				break
			}
			if resp != nil {
				resp.Body.Close()
			}
			time.Sleep(20 * time.Millisecond)
		}
	}
}

func put(t *testing.T, c *http.Client, base, key, value string) (int, resp) {
	t.Helper()
	bs, _ := json.Marshal(map[string]string{"value": value})
	req, _ := http.NewRequest(http.MethodPut, base+"/kv/"+key, bytes.NewReader(bs))
	req.Header.Set("Content-Type", "application/json")
	r, err := c.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer r.Body.Close()
	raw, _ := io.ReadAll(r.Body)
	var out resp
	if r.StatusCode == 201 {
		_ = json.Unmarshal(raw, &out)
	}
	return r.StatusCode, out
}

func get(t *testing.T, c *http.Client, base, prefix, key string) (int, resp) {
	t.Helper()
	r, err := c.Get(base + prefix + key)
	if err != nil {
		t.Fatal(err)
	}
	defer r.Body.Close()
	raw, _ := io.ReadAll(r.Body)
	var out resp
	if r.StatusCode == 200 {
		_ = json.Unmarshal(raw, &out)
	}
	return r.StatusCode, out
}

func rawGet(t *testing.T, c *http.Client, base, prefix, key string) (int, string) {
	t.Helper()
	r, err := c.Get(base + prefix + key)
	if err != nil {
		t.Fatal(err)
	}
	defer r.Body.Close()
	raw, _ := io.ReadAll(r.Body)
	return r.StatusCode, string(raw)
}