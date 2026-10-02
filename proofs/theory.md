# Origin-preserving cut contracts

This document gives mathematical arguments for the finite calculus implemented in this repository. The arguments are pen-and-paper proofs, not proof-assistant-checked metatheory. Executable exhaustive checks, certificate replay, and mutation tests are separately reported as finite validation. Integer encoding and enumeration ceilings in the implementation are resource restrictions, not semantic counterexamples.

## 1. The model and its observations

Let S be a nonempty finite set of immutable source-generation identities and P a nonempty finite set of boundary ports. An input clock valuation consists of birth times b_s for s in S and port readiness times r_p for p in P, all integers measured in a single time coordinate whose current cut is zero. Every readiness is nonnegative. Birth times may be negative, zero, or positive. Positive birth times describe declared future source generations, not already observed payloads.

A port carries a term of the free algebra

    q ::= unit | src(s) | pair(q,q).

The source set L(q) is empty for unit, {s} for src(s), and the union of its two argument sets for pair. Causality requires b_s <= r_p whenever s belongs to L(q_p). Different appearances of src(s) denote the same immutable generation, not fresh generations with coincidentally equal values. Substituting actual source values into a term determines a payload. Term equality therefore establishes payload equality for all assignments in this free algebra. No arithmetic simplification, branch on a value, mutable cell, or timestamp inspection is implicit in the term language.

An interface denotes a nonempty bounded set Omega of integer input valuations satisfying causality. The implemented representation is a finite union of bounded difference zones. A zone is a conjunction x_v - x_u <= c with integer c, including lower and upper bounds on all variables and a distinguished zero variable fixed to zero. The syntax uses an edge (u,v,c) to mean this inequality. Each initial encoded zone must be feasible. Empty zones obtained by conditioning an observation may be discarded only with negative-cycle evidence.

A continuation is a finite directed acyclic graph. Every non-port vertex is a copy with one ordered data dependency, a pair with two ordered data dependencies, or a barrier with no data dependencies. It may additionally have control dependencies, called gates. Its complete dependency set D(v) is the disjoint union of its data dependencies and gates and must be nonempty. An edge e=(u,v) has an independent integer delay delta_e in [l_e,u_e], with 0 <= l_e <= u_e. All combinations of interface valuations and edge delays are allowed. This rectangular independence is used for exact runtime residualization. The weaker condition that every interface valuation can be paired with the all-upper delay vector suffices for the worst-age theorem.

A port fires once at r_p. A firing sends one message on every outgoing edge. A non-port fires eagerly once all its incoming messages have arrived. Its time is

    t_v = max_{u in D(v)} (t_u + delta_(u,v)).

Copies and pairs use only their data dependencies to construct their payloads. Barriers produce unit. Gates delay execution without importing their payload's source identities. All events, including zero-delay events newly enabled at a time, are processed before advancing the time coordinate.

An output policy assigns unique logical keys k to a designated vertex o_k, an expected term q*_k, and a nonnegative deadline Delta_k. An output must have nonempty data lineage. Its age at emission is

    age(k) = t_(o_k) - min_{s in L(q_(o_k))} b_s.

This is age of the oldest contributing generation at emission, not the continuously increasing age of a displayed last-known value between outputs. An execution observation maps keys to payload terms, emission times, and ages. Two legal delay schedules need not give the same emission times or arrival order. The determinism claim concerns the key-to-term map. Simultaneous independent events may be permuted without changing times or payloads.

A location label may be attached to each vertex and an epoch index to each installed graph. Neither supplies an extra guarantee. The calculus assumes declared finite transport/processing bounds and a common time coordinate. It does not derive physical clock synchronization, queueing bounds, replica consistency, epoch ownership, a distributed snapshot protocol, or a real deployment's ability to install a graph atomically.

## 2. Eager execution and principal freshness rows

### Lemma E1 (finite eager execution)

For any interface valuation and legal delay vector, every vertex of an acyclic continuation fires exactly once, at the recursively defined time above, and its term is determined by the graph and port terms. All these times are finite. Nonnegative delays and input causality imply b_s <= t_v for every s in L(q_v).

**Proof.** Choose a topological ordering with ports first. Ports fire once at their finite readiness times. For a non-port v, all its predecessors occur earlier in the ordering and, inductively, each fires once and sends exactly one message to v. Every such message arrives at a finite time because its delay is finite. The last arrival enables v; eager firing assigns precisely their maximum and occurs once because no second message exists for any dependency. The constructor selected at v is fixed, and its data arguments are inductively fixed. A contributing birth is no later than a data predecessor's firing and hence no later than v's firing. Induction covers every vertex. Equal-time queue order only permutes causally independent processing: the maximum-arrival time and ordered constructor arguments remain the same. This proves the statement without treating numerical solutions of cyclic max equations as executable runs. In particular, a zero-delay cycle has no first firing and is not rescued by a putative all-zero solution. QED.

Define the rectangular readiness-origin profile

    F_(p,s) = max_{omega in Omega} (r_p - b_s).

All entries exist and are finite because Omega is nonempty and bounded. A cross entry can be negative when an unrelated source is born later than a port is ready. Own-lineage entries are nonnegative by causality.

For every vertex v define a row G_v indexed by all of S and a term q_v. At a port, G_p=F_p and q_p is its interface term. At a non-port,

    G_(v,s) = max_{u in D(v)} (G_(u,s) + upper_(u,v)),

while q_v is copied, paired, or unit according to the operator. Data lineage is L(q_v), not the union of all gating predecessors' lineages.

### Theorem F1 (exact rows and principal age bounds)

For every vertex v and source s,

    G_(v,s) = max_{omega,delta} (t_v - b_s).

Consequently the exact worst emission age of output k is

    A_k = max_{s in L(q_(o_k))} G_(o_k,s).

An output satisfies its declared age bound for all executions exactly when A_k <= Delta_k. Its key has the expected free-algebra term for all assignments exactly when q_(o_k)=q*_k.

**Proof.** Let M_(v,p) be the maximum sum of upper edge delays on a directed path from p to v, or minus infinity when there is no such path; a port has its own empty path of weight zero. Expanding the eager max recurrence along the finite DAG gives

    t_v(delta) = max_{p, path p -> v} (r_p + sum_{e in path} delta_e).

For a fixed input valuation, each summand is bounded above by its all-upper value. The all-upper vector is itself allowed and realizes equality for every vertex simultaneously. Therefore

    max_{omega,delta}(t_v-b_s)
      = max_p (M_(v,p) + max_omega(r_p-b_s))
      = max_p (M_(v,p) + F_(p,s)).

The local row recurrence evaluates exactly this path expression. Exchanging these finite maxima does not require all cells of F to be simultaneously attainable. For a single maximizing cell (p,s), choose a valuation attaining that cell and the all-upper delay vector. Its selected path attains the displayed value, and the universal upper bound prevents any overshoot. Finally t-min b is max_s(t-b_s) over the finite nonempty data lineage, so a further exchange of maxima gives A_k. A violating maximum supplies an actual stale-output witness. Free-algebra constructor equality is sufficient for equal values under every assignment; different free terms denote distinct symbolic observations, which is the equality tested here. QED.

### Corollary F2 (composition and uniform rebasing)

For a fixed continuation segment exposing a new boundary Q, its profile is F'=M tensor F, where tensor is max-plus matrix multiplication and M contains longest upper path weights. A later independent segment N has profile N tensor (M tensor F)=(N tensor M) tensor F, with data terms/lineages carried separately. Replacing every readiness, birth, and event timestamp by that timestamp minus the same constant leaves all corresponding age differences unchanged.

**Proof.** Apply F1 at each exposed vertex. Matrix associativity follows by reordering the finite maxima and associating integer addition, including the unreachable-path convention. Time translation cancels in every difference. This is an exact freshness summary of the actual image of the preceding segment; it is not a claim that the profile reconstructs that image's joint timed traces. QED.

## 3. Difference-zone evidence

### Lemma Z1 (difference feasibility evidence)

A feasible potential x with x_zero=0 and x_v-x_u<=c for every zone edge proves nonemptiness. A directed cycle whose edge weights sum to a negative number proves emptiness. For a bounded integer difference system, exactly one of these two forms of evidence exists.

**Proof.** The first claim is direct substitution. Summing all inequalities along a cycle cancels the variables and yields 0 <= sum c; a negative sum contradicts feasibility. Conversely, assume there is no negative cycle. Adjoin a source with zero-weight edges to all vertices, or initialize all shortest-path distances to zero. Shortest distances exist because negative cycles are absent. They satisfy d(v)<=d(u)+c on every edge. Set x_v=d(v)-d(zero). All inequalities and the zero gauge hold; included bound edges ensure that x is a bounded legal valuation. Integer edges give integer distances. Bellman--Ford either supplies such distances or a predecessor cycle of negative total weight; the checker need only verify the resulting evidence, not trust that algorithm. QED.

### Lemma Z2 (exact cell evidence)

In a nonempty bounded zone, F_(p,s) is the shortest-path distance from the birth variable b_s to the readiness variable r_p. It is certified by a path of that weight and a feasible potential attaining the difference. For each fixed s one feasible potential can attain every port entry of that column at once.

**Proof.** Summing along any such path gives r_p-b_s <= its weight. Bound edges connect all variables through zero, so a finite shortest path exists. Take d(v) to be shortest distance from b_s to v and normalize x_v=d(v)-d(zero). Triangle inequalities make x feasible. Since there is no negative cycle, d(b_s)=0, and hence x_(r_p)-x_(b_s)=d(r_p). This is the upper bound with equality. A shortest path can be made simple by deleting nonnegative cycles, so it needs at most |V|-1 edges. The single normalized distance potential works for all destinations in the column. QED.

For a finite union, take the componentwise maximum of component profiles. The replay kernel checks every component, every source column, every readiness path, and the feasibility/tightness potentials. An omitted union member or an incorrect empty-member declaration would be unsound and is not accepted. Initial inputs with an infeasible listed member are diagnosed as inadmissible encodings. Conditioning at runtime has its own explicit negative-cycle certificates and can therefore safely remove newly empty members.

## 4. Contextual completeness and information cost

A source-complete port interface has, for every s, a designated port d(s) whose term is exactly src(s). Other ports may carry arbitrary terms. Compare two interfaces Omega and Gamma having the same ports, origins, and port terms. A test context is any finite clock-oblivious acyclic graph from Section 1, with any finite nonnegative interval constants and any fixed output deadlines. Write Omega <=ctx Gamma when every such context fresh under Gamma is also fresh under Omega. Constructor policies are the same in the compared contexts.

### Theorem C1 (contextual order)

For source-complete interfaces,

    Omega <=ctx Gamma  iff  F^Omega <= F^Gamma entrywise.

In particular equality of profiles is exactly indistinguishability by these universal freshness tests. This does not assert equivalence for arbitrary programming contexts, timestamp-dependent branches, mutable state, or joint-trace observations.

**Proof.** The forward-useful direction follows from F1: all path weights and lineage selections are the same, and maximum and addition are monotone. For necessity suppose F^Omega_(p,s)>F^Gamma_(p,s). If p=d(s), use a copy of p with any fixed nonnegative delay D. Its worst age differs by exactly the displayed cell difference. Otherwise use a copy whose only data dependency is d(s) with delay zero and whose gate is p with fixed delay D. Choose an integer

    D >= max(0, F^Omega_(d(s),s)-F^Omega_(p,s),
                  F^Gamma_(d(s),s)-F^Gamma_(p,s)).

The gate branch then attains the maximum in both interfaces, so their exact worst ages are D+F^Omega_(p,s) and D+F^Gamma_(p,s). Both are nonnegative because they dominate the data port's causal own-age entry. Set the deadline to the latter value. Gamma passes and Omega fails. The context obeys the syntax, has a singleton data lineage, and uses finite nonnegative constants. This contradicts contextual order and proves necessity. QED.

### Theorem C2 (quadratic information lower bound within a single zone)

Fix n>=1 and integer K>=1. There is a family of (K+1)^(n^2) source-complete single-zone interfaces with n ports and n origins, fixed singleton term metadata, and pairwise different contextual freshness behavior. Therefore any lossless exact representation for all these context tests requires at least n^2*log2(K+1) bits in the worst case, apart from fixed metadata.

**Proof.** For any matrix B in {K,...,2K}^(n*n), give all readiness clocks bounds [0,K] and all births bounds [-K,0]. For every cell impose r_i-b_j<=B_ij, and let port i carry exactly src(s_i). The bounds make every own-port causality inequality b_i<=r_i automatic. The all-zero valuation witnesses nonemptiness. The imposed constraint gives the desired upper bound for a cell (i,j). To attain it set r_i=K, all other readiness clocks zero, b_j=-(B_ij-K), and all other births zero. The target difference equals B_ij. Every other difference is at most K, while every other matrix bound is at least K. Bounds and causality hold. Thus the profile is exactly B. C1 separates every different pair of matrices. An encoding that answers all context tests exactly must distinguish all these interfaces, requiring n^2*log2(K+1) bits in the worst case. Each matrix entry uses O(log(K+1)) bits, matching this scaling. The result concerns a family of uncertain interfaces, not every concrete snapshot: when births are fixed the profile factors as max(r_i)-b_j and has a linear-size factorization. QED.

### Theorem C3 (the static quotient for opaque payload ports)

For any finite bounded interfaces with identical port terms and at least one data-bearing port, define

    C(q,p)=max_{s in L_p} max_Omega(r_q-b_s)

for every timing port q and every data-bearing payload port p. Then Omega <=ctx Gamma for fixed, clock-oblivious constructor graphs if and only if C^Omega is entrywise at most C^Gamma.

**Proof.** For an output, its lineage is the union of the lineages of the input ports used in its constructor tree. F1 writes its worst age as a maximum of path-upper constants plus C(q,p) over the timing ports q with a dependency path and the payload input ports p in that tree. Entrywise order therefore suffices. If a cell (q,p) is larger in Omega, emit a copy of the entire value of p, with a gate from q delayed by a sufficiently large fixed D. For q=p a single delayed data edge suffices, avoiding duplicate parents. Choose D so that the q path dominates the data-ready path in both interfaces. Its worst ages are respectively D+C^Omega(q,p) and D+C^Gamma(q,p); a deadline at the latter separates them. Bounds ensure a finite nonnegative D exists. QED.

Thus singleton source ports were a convenient way to expose each original profile column, not a necessary restriction on exact static contextual reasoning. The profile F is still useful for composing arbitrary graphs and is exactly checked by the implementation. C is the smaller observation quotient when the available payloads hide individual origins.

## 4A. What changes when a controller can observe time?

The contextual theorem C1 deliberately excludes a controller that selects a new continuation after observing timestamps. For the next results an adaptive context may inspect input-readiness times, event firings, and message receipts, but it must not inspect source births, computed ages, or any metadata from which births are directly recovered. It has a finite bound on reconfigurations, uses finite independent delay intervals, and eventually produces its required keyed constructor outputs. It may retain observed timestamps in local state. The input port terms and origin identifiers are the same on both sides of a comparison. The controller's choices and event timing therefore depend on the readiness vector and edge delays, not on the birth vector. This is a mathematical extension of the fixed-graph context class, not a claim that the JSON language executes arbitrary controller programs.

For a bounded nonempty interface Omega define its readiness support R_Omega and conditional origin-age envelope H by

    R_Omega = { r : there exists b with (r,b) in Omega },
    H_Omega(s,r) = max { -b_s : (r,b) in Omega }    (r in R_Omega).

The zero coordinate r_zero=0 is included for convenience. The maximum exists over a finite nonempty fiber. The negative birth is a coordinate quantity, not an emission age; it may be negative for a future source. Actual emission ages remain nonnegative by data causality.

For each data-bearing port p, let L_p be the nonempty set of origins in its constructor term and define K_Omega(p,r)=max_{s in L_p} H_Omega(s,r). At least one such port is required. Other ports may carry unit. The language has constructors but no projections: every output lineage is a nonempty union of port lineages.

### Theorem A1 (adaptive freshness order for opaque payloads)

On interfaces with the same port terms and at least one data-bearing port, every birth-blind adaptive context fresh under Gamma is fresh under Omega if and only if

    R_Omega is a subset of R_Gamma, and
    K_Omega(p,r) <= K_Gamma(p,r)
        for every r in R_Omega and every data-bearing port p.

Here a context's keys and deadlines are fixed; its finite internal reconfiguration strategy can depend on its timestamp observations. The theorem compares universal per-key age obligations, not the joint set of possible output ages or an observer allowed to read births.

**Proof, sufficiency.** Fix an execution under Omega, its readiness vector r, and all choices of independent edge delays along its adaptive history. By support inclusion Gamma has valuations with the same r. Pair either environment with these same delay choices. Induct on the finite controller history. Initially the port values, readiness events and controller state are the same. Every subsequent operator firing and receipt depends on readiness, delays and previous choices, not on births. Thus the controller sees the same observations, makes the same edits, and emits the same terms at the same times in the two executions. The argument also transfers progress in this finite context class.

Consider an output at time T and select an origin s of its payload that is oldest in the fixed Omega execution. Some input data-bearing port p used to construct this output contains s. Its age is T-b_s <= T+K_Omega(p,r) <= T+K_Gamma(p,r). In Gamma there is an origin t in L_p and a birth valuation attaining K_Gamma(p,r); selecting that valuation leaves the paired history unchanged. The output retains t, since constructors do not project away origins. That Gamma output has age at least T+K_Gamma(p,r). A stale Omega execution would therefore imply a stale Gamma execution with the same controller and delays. This contradicts the assumed freshness of the context under Gamma. Repeat for every required key. Different outputs may select different attaining Gamma valuations; universal safety does not require one valuation to attain all their maxima simultaneously.

**Proof, necessity.** A separating context first observes all input readiness times, finishing this observation at T(r)=max_p r_p, then emits the entire constructor value of a designated data-bearing port p. It may wait a chosen additional nonnegative integer D exactly when the full readiness vector equals one designated r*, and otherwise waits zero. This can be realized with buffered data copies, an all-readiness barrier, and a finite logical reconfiguration after the barrier; births are not inspected. In detail, initially buffer p on a zero-delay edge into the output copy and gate that copy by the all-readiness barrier with delay one. The barrier fires at T(r). At its closed cut, the data are buffered but the output is pending. The controller replaces the pending copy by one gated on the local cut clock with delay D or zero. The extra unit in B below makes even the unedited initial epoch fresh under Gamma, and each reachable Gamma edit is admitted against its conditioned residual interface. In the finite oracle it is instantiated directly as an observation-controlled local timer and a gated copy.

If r* belongs to R_Omega but not R_Gamma, fix any data-bearing p and let B=1+max_{r in R_Gamma}(T(r)+K_Gamma(p,r)). Causality makes B positive. Choose D=max(0,B-T(r*)-K_Omega(p,r*)+1). Under Gamma the special branch is never taken and all ages are at most B. Under Omega the special branch has an attaining birth valuation and age at least B+1. The deadline B separates the interfaces.

Otherwise suppose support inclusion holds but K_Omega(p,r*)>K_Gamma(p,r*) at some r*,p. With B defined as before, set D=B-T(r*)-K_Gamma(p,r*) >=0. The exceptional Gamma age is at most B and all its ordinary branches are also bounded by B. Omega has an exceptional age B+K_Omega(p,r*)-K_Gamma(p,r*)>B. Again the deadline B separates the interfaces. These contexts use only bounded observations, a finite timer, a fixed key and term, and a constant deadline. QED.

### Lemma A2 (a single zone's conditional earliest births)

Let D_uv be the closed difference bound x_v-x_u<=D_uv for a bounded nonempty integer zone. Let I be its readiness variables together with zero. Its readiness support is exactly the projected zone

    Q = {r : r_zero=0 and r_j-r_i<=D_ij for all i,j in I}.

For every r in Q, the values

    ell_v(r) = max_{i in I}(r_i-D_vi)

form a feasible full clock valuation extending r and simultaneously minimize every unfixed clock. In particular

    H(s,r) = min_{i in I}(D_(b_s,i)-r_i).

**Proof.** Every original valuation satisfies the projected constraints. Conversely, take r in Q. For a fixed coordinate j in I the projected constraints imply r_i-D_ji<=r_j for every i; choosing i=j gives equality because D_jj=0. Thus ell_j=r_j, including the zero gauge. For any original edge u->v of weight c, shortest-path closure gives D_ui<=c+D_vi. Hence r_i-D_vi<=c+r_i-D_ui for every i. Taking maxima gives ell_v<=ell_u+c. All constraints, explicit bounds and data causality are represented by such edges, so ell is feasible. Any other extension x of r must satisfy r_i-x_v<=D_vi, hence x_v>=ell_v for each v. This proves simultaneous minimality. Taking minus the birth coordinate yields the displayed minimum formula. All values are integers. QED.

The type for this observer class can therefore consist of Q and the source-to-readiness/zero submatrix of D. Birth-to-birth constraints influence these closed bounds, but need not be retained separately to answer the adaptive freshness tests. This is a semantic sufficiency statement about the extracted type; the current proof certificate deliberately retains a full closure and is not a certificate-size optimization.

### Theorem A3 (exact row-cover criterion for a single zone)

Let Omega and Gamma be bounded nonempty single zones with the same opaque port terms and at least one data-bearing port. Write A_s(i)=D^Omega_(b_s,i) and B_t(i)=D^Gamma_(b_t,i), for i in the readiness/zero index set I. Then adaptive refinement holds exactly when

    D^Omega_ij <= D^Gamma_ij                      for all i,j in I,
    for every data-bearing port p and s in L_p,
        there exists t in L_p with A_s(i)<=B_t(i) for every i in I.

The second condition is a finite cover of origin rows, restricted to the origins actually visible together in one opaque payload. A dominating right origin need not have the same identifier as the left origin. No extra difference-feasibility query or readiness enumeration is necessary.

**Proof, support.** A2 gives the projected readiness zone. Entrywise closed-bound inclusion implies support inclusion. If D^Omega_ij>D^Gamma_ij, the normalized shortest-distance potential from i in Omega attains that difference and violates the corresponding Gamma bound. Thus this condition is also necessary.

**Proof, row-cover sufficiency.** Assume support inclusion and a right row B_t dominating A_s. At every common readiness vector r, min_i(A_s(i)-r_i)<=min_i(B_t(i)-r_i). By A2 this is H_Omega(s,r)<=H_Gamma(t,r). Taking the maximum over s in L_p and choosing a (possibly different) dominating t for each s proves K_Omega(p,r)<=K_Gamma(p,r). A1 now gives adaptive refinement.

**Proof, row-cover necessity.** Suppose one port p and left origin s have no dominating right origin in L_p. For every t in L_p choose a column j_t with A_s(j_t)>B_t(j_t). Consider the full Omega shortest-distance potential from b_s, normalized at zero. Its readiness vector is

    r_i = A_s(i)-A_s(zero).

It is a feasible Omega valuation by Z2, hence belongs to Gamma's readiness support by the first condition. All left minimum branches are equal at this vector, so H_Omega(s,r)=A_s(zero). For every t in L_p,

    H_Gamma(t,r)
      = A_s(zero)+min_i(B_t(i)-A_s(i))
      <= A_s(zero)-1.

Consequently K_Omega(p,r)>=A_s(zero)>K_Gamma(p,r). A1 supplies a concrete one-decision separating reconfiguration. This witnesses failure even when no singleton source port exists. QED.

An accepted certificate consists of two exact closed-matrix certificates and, for each p,s, a same-payload dominating right origin. A rejected support comparison names one readiness pair; a rejected age comparison names p,s and one separating column for every right origin in L_p. The already certified left potential is an attaining concrete witness. Replay performs exact integer comparisons and path/potential checks; it does not run shortest paths, solve feasibility queries, or enumerate controllers.

With V=1+P+S clocks and E constraint edges, Floyd--Warshall closure takes O(V^3) arithmetic operations. Extracting all simple tight paths through adjacency lists takes O(VE+V^3), including explicit path copying. Row comparison takes O(P^2+(P+1)*sum_p |L_p|^2). Reading expanded port terms costs their total representation length. The explicit full-closure certificate uses O(V^3) path indices plus O(V^2) distances and potentials, before integer and index bit lengths are accounted for. These are arithmetic-operation bounds, not constant-time claims for unbounded integers.

Within each payload, remove duplicate and coordinatewise dominated origin rows. The resulting maximal-row antichain has the same K function. Under equal readiness supports, A3 says that two payloads have the same K exactly when their maximal-row antichains coincide as sets of numeric rows. Proof: mutual finite row cover forces each maximal row to coincide with a maximal row on the other side. Origin names attached to otherwise equal numeric rows do not affect this particular freshness observation, although actual constructor terms and their origin identifiers remain fixed and checked separately. This gives a canonical numeric observation type for the single-zone fragment, not a complete trace representation.

For a singleton source-complete interface, the cover specializes to direct comparison of each birth-to-readiness/zero row. A direct approach could make S*(P+1) difference-feasibility queries, but these are unnecessary: at the normalized left row all branches attain together. For multiple zones, A1 remains valid, but the closed-row theorem does not apply memberwise. Conditional envelopes range over only those members compatible with r. No polynomial-time claim or implemented adaptive decision procedure for arbitrary unions is made here.

### Strict boundaries between the observation classes

Static profiles alone are insufficient for A1 even for one zone. Give both sources birth zero. Let both ports range over readiness [0,2] in Omega, and restrict p to [1,2] in Gamma while q still ranges over [0,2]. Every static cross-profile entry is two. A controller that waits five ticks when p is ready at zero and otherwise immediately emits after observing all ports has worst ages seven and two. The static theorem is not contradicted because this controller observes time.

The zero column of A2 also carries information absent from the original static profile. Let r_p=r_q in [0,2]. In Omega set b_a=b_b=r_p-2; in Gamma set both births to zero. Their readiness supports and static cross profiles coincide (every cell is two), but at readiness zero their conditional oldest ages are two and zero. A readiness-conditioned controller separates them. The additional birth-to-zero bounds distinguish the types.

Conversely, adaptive freshness does not determine the full joint output-age trace. At readiness zero, a source with birth in [-1,0] and a source fixed at -1 both have H=1. Their actual possible ages differ, even though every birth-blind universal freshness test has the same worst case. With two sources, independent and equal births in [-1,0] likewise have the same conditional envelope but different joint age pairs. R3's full continuation correspondence is stronger than these per-key freshness equivalences.

Source completeness matters to the per-origin criterion, but is unnecessary for A1 and A3. With only one port carrying pair(src(a),src(b)) at time zero, swap births (-2,0) and (0,-2). Without projection operators every non-unit observable term retains both origins and has oldest age two. A controller cannot isolate one origin, though their individual profile columns differ. A3 correctly accepts this exchange by matching each left oldest-origin row with the other right origin in the same opaque payload. A comparison that insists on matching identical source names would falsely reject it. Single-zone nonempty residual interfaces with data-bearing outputs meet this generalized term boundary; a multi-zone residual still lies outside the implemented adaptive decider.


### Theorem A4 (revealing all births restores exact input-state inclusion)

Suppose a controller can observe the complete readiness and birth vector after all inputs are ready, and at least one payload is available. Every such finite context fresh under Gamma is fresh under Omega if and only if Omega is a subset of Gamma as full clock-valuation sets.

**Proof.** Inclusion couples the identical full valuation, timer choices and execution, hence preserves every freshness obligation. Conversely choose a full valuation w* in Omega but not Gamma. Observe all inputs at T=max r_p and their birth metadata. Select any nonempty payload p. Use the same initial barrier and unit output delay as A1, with B=1+max_{w in Gamma}(T(w)-min_{s in L_p}b_s). Emit immediately on every observed vector except w*, where the controller waits max(0,B-T(w*)+min_{s in L_p}b_s+1). Under Gamma the special branch is unreachable and every age is below B; under w* the output is at least B+1. The finite support makes the constants finite and the comparison is exact. QED.

This theorem is a boundary result, not an implemented birth-aware controller runtime. It explains why hiding birth metadata is a real restriction rather than an innocuous optimization: allowing that observation invalidates both the static matrix quotient and the adaptive antichain quotient.

## 5. Observed prefixes with uncertain source clocks

A timestamped prefix at cut tau>=0 contains (i) every event that fired at a time <=tau, with its firing time, and (ii) every incoming-edge message received at a time <=tau, with its receiver, sender, and receipt time. It contains no scheduled future receipt time. Observation is closed through all zero-time consequences at tau.

The prefix conditions are as follows. The graph is acyclic. All recorded event times lie in [0,tau]. Every recorded receipt names a real edge, is unique, has a fired sender, lies in [0,tau], and differs from the sender time by an allowed delay. A non-port is recorded as fired exactly when all its incoming receipts are recorded; if fired its time equals their maximum. For a fired sender with an unrecorded outgoing receipt, sender_time+upper_delay must be strictly greater than tau. Finally condition the original interface by r_p=fired_time for recorded ports and r_p>=tau+1 for all unrecorded ports; the resulting union of zones must be nonempty. Every zone is classified using Z1 evidence. These conditions use the integer time model: the strict inequality is represented by tau+1, not by a dense-time approximation.

### Theorem R1 (prefix realizability)

These conditions are necessary and sufficient for the timestamped prefix to be the closed observation of at least one legal original execution.

**Proof.** Necessity follows directly from event semantics and interval bounds. For sufficiency choose a valuation in a feasible conditioned input zone. This fixes all recorded input times as observed and places every other input strictly after tau. On a recorded edge receipt choose its delay to be receipt_time-sender_time. For a fired sender with an unrecorded receipt choose any integer delay at least max(lower,tau+1-sender_time) and at most upper; the stated strict-upper condition makes this interval nonempty. For edges from unfired senders choose any original legal delay. These choices are independent of the input zone and of one another.

Run the graph in topological order. Every recorded port fires at its observed time; every unrecorded port is later than tau. At a recorded non-port all its predecessors are recorded (a receipt could not precede an unrecorded sender), its incoming arrivals are the specified ones, and their maximum equals its recorded time. At an unrecorded non-port at least one incoming receipt is missing, since otherwise closure would require a firing. Such a receipt either comes from a recorded sender and has been placed after tau, or comes from an unrecorded predecessor, whose firing is after tau by induction. Nonnegative delays put the latter receipt after tau too. Thus no unrecorded non-port fires by tau. All receipts from unrecorded senders are also after tau. The constructed run has exactly the observed events and receipts, including closure at tau. QED.

### Construction R (residual interface and graph)

First condition every original input zone as in R1 and discard only those certified empty. Every completed input readiness variable has a known constant value T_p. Retain all births and all uncompleted input readiness variables. Rebase every retained nonzero clock by x'=x-tau and eliminate each completed input clock by its observed constant. For an original difference inequality x_v-x_u<=c, write x_v=y_v+a_v and x_u=y_u+a_u, where a=tau for retained variables, a=T_p and y=zero for completed readiness clocks, and a=0,y=zero for the original gauge. The transformed inequality is

    y_v-y_u <= c+a_u-a_v.

This is substitution, not a projection of an unknown clock. It preserves each conditioned zone exactly and introduces no alternatives. Retained input readiness intervals are intersected with [1,infinity).

Remove every fired non-port and every completed original port. For each individual edge from a fired sender u to a pending receiver v create a fresh boundary port carrying q_u. If its receipt has already been observed, this port is ready at zero. Otherwise give it the independent readiness interval

    [max(1,T_u+lower_(u,v)-tau), T_u+upper_(u,v)-tau].

Replace that edge into v by a zero-delay edge of the same data or control kind. Keep edges whose senders are still pending unchanged. The new boundary clocks have the indicated intervals independently of the conditioned input clocks. A unit-valued cut-clock port ready at zero supports explicit installation gates. Drop already emitted output keys; retain every other key, expected term, and deadline. No birth identity is changed, and every retained birth coordinate is b'_s=b_s-tau.

### Lemma R2 (positive pending work)

In every execution consistent with the prefix, every original pending event fires strictly after tau. In every valuation of Construction R, each residual event corresponding to an original pending event fires strictly after zero.

**Proof.** The first statement was established in the sufficiency proof of R1 for arbitrary legal choices. For the residual statement, pending original input ports have readiness at least one. A pending non-port has a missing incoming receipt. It either comes from a pending predecessor, positive by topological induction, or is represented by an in-flight crossing port whose lower bound is at least one. Other incoming dependencies may be buffered at zero; the maximum nevertheless stays positive. QED.

### Theorem R3 (exact non-quiescent residualization without zone splitting)

Project away the fresh boundary-port events in Construction R. Its executions have exactly the same future original-event times, remaining output keys, payload terms, and emission ages as the original executions consistent with the observed prefix, with event/output times translated by -tau. Future original-message receipts can likewise be recovered; already received messages belong to the fixed prefix. The residual representation uses no more difference zones than the original interface, and creates one port per fired-to-pending crossing edge plus one cut clock.

**Proof, original to residual.** Take an original execution realizing the prefix. Retained clocks are rebased; fixed completed input clocks are substituted; therefore every transformed inequality holds. For a crossing edge already received, expose its sender term at time zero. For an in-flight edge expose it at its actual receipt time minus tau, which lies in the stated interval. Preserve all pending-sender edge delays. These choices satisfy residual causality: every origin of a completed sender was born no later than its firing, which is at most tau, so the rebased birth is <=0 and hence <=any newly exposed readiness. Retained pending ports keep their original causal inequalities.

Induct on original pending events. For a pending input, equality of times is its definition. For a pending non-port, every incoming arrival originally after tau is represented by exactly its translated positive time, either as an in-flight boundary port or as a pending predecessor's translated time plus its unchanged delay. An already buffered receipt at time a<=tau is represented by zero rather than a-tau<=0. R2 guarantees at least one positive incoming dependency. Replacing other nonpositive arguments of a maximum by zero cannot change that positive maximum. Thus the residual firing is t_v-tau. Constructor terms are unchanged because only completed terms replace their corresponding data inputs; control edges remain control edges. Each remaining output preserves its key and its lineage, and (t_v-tau)-(b_s-tau)=t_v-b_s, so ages agree.

**Proof, residual to original.** A residual valuation belongs to the transform of some retained original zone. Reverse the affine map for all retained clocks and set every removed input clock to its observed constant. The transformed inequalities ensure that this is a legal conditioned original valuation. Restore the recorded delay for every observed receipt. For every in-flight crossing edge choose delay r'_cross+tau-T_sender; its interval and strict lower bound make this a legal, unreceived-by-tau original message. For edges from pending senders use their residual delays. These choices are independent, so together they form a legal full delay vector. R1 gives the exact prefix; the same positive-maximum induction gives equality of every future original event and output. Duplicate profiles or overlapping zones do not matter because semantics takes their set union.

At no step is a choice of maximizing predecessor guessed. Completed maxima have observed numerical timestamps; pending maxima remain graph nodes. Constant substitution maps one conditioned zone to one zone, independent interval products add variables but not disjuncts, and empty-zone filtering only removes members. This proves the cardinality bound as well as the two directions. QED.

## 6. What coarser observation loses

### Theorem O1 (an exponential zone-cover cost for receipt-blind cuts)

There are finite acyclic programs with n pending joins such that an observation listing completed events but not individual message receipts requires at least 2^n difference zones to represent the exact joint crossing-readiness possibilities. Exactly 2^n zones suffice. The claim is about explicit unions of difference zones, even allowing auxiliary variables later projected away; it is not a lower bound for arbitrary Boolean formulas, general polyhedra, worst-age profiles, or all abstract domains.

**Proof.** For each i make two distinct input ports ready at zero and one join depending on both, with independent edge delays x_i,y_i in {0,1}. Observe at cut zero that all these ports fired and all n joins are still pending, but omit receipt records. Eager closure says exactly that (x_i,y_i)!=(0,0) for every i. Thus the set of crossing readiness vectors is

    H_n = {(x_i,y_i)_i in {0,1}^{2n} : x_i=1 or y_i=1 for every i}.

A difference zone is closed under componentwise minimum. Indeed, if x and y satisfy v-u<=c and z=min(x,y), choose whichever of x_u,y_u is z_u; then z_v is no larger than the corresponding v coordinate, giving z_v-z_u<=c. The argument preserves bounds, the zero gauge, and integrality. Projections of zones are minimum-closed too: choose witnesses for two projected points and take the componentwise minimum of the entire witnesses.

There are 2^n vectors in H_n with exactly one coordinate equal to one in every pair. For any two distinct such vectors, their componentwise minimum has (0,0) in at least one pair and lies outside H_n. Therefore no zone contained in H_n can contain two of these vectors. Any exact union needs at least 2^n members. Conversely, for each of the 2^n choices of one coordinate in every pair, impose that chosen coordinate=1 while retaining [0,1] bounds on the other coordinates. Their union is exactly H_n. QED.

The original pending joins all fire at time one in this construction. Thus merely checking those old output maxima does not reveal the lost joint possibilities. Reconfiguration can expose or separately reuse the crossing inputs, making their joint availability relevant. This explains why full continuation-set checks and worst-age checks are distinct obligations. A factorized Boolean representation could keep H_n compact; the theorem does not rule that out.

## 7. Admission and finite sequences of updates

An admitted program has an acyclic dependency order, the expected constructor term at every output, and A_k<=Delta_k from F1. At a valid prefix, an edit must inherit the residual's complete port/origin/zone interface and the same map from remaining keys to (expected term,deadline). It may alter the pending graph and the vertices bound to those keys. Freshness and term obligations are then checked again. Changing a birth bound, dropping a key, or weakening a deadline is not admission against the inherited policy.

If installation takes a declared fixed integer h>=0, add a unit barrier with delay h from the cut clock and a zero-delay gate from that barrier to every new computation. A bare-port output is wrapped in a gated copy. This is a semantic installation allowance, not a measurement or a proof of a runtime installer's wall-clock behavior. More general independently bounded installation delays can be represented explicitly in the graph; the implemented helper uses a fixed allowance.

### Theorem U1 (freshness-preserving finite update sequences)

Start with an admitted program and its fixed logical output policy. Consider a finite sequence of valid timestamped prefixes and admitted replacement graphs, with every assumed installation/edge/input delay bound obeyed. Every emitted key has its original expected term and age at most its original deadline. No key is emitted twice. After the last edit, every remaining required key is eventually emitted. Hence the complete key-to-term map is deterministic although output timing and ordering can vary.

**Proof.** Induct on update epochs. In an admitted epoch, E1 and F1 establish deterministic constructor terms, finite progress, and every output deadline for every legal valuation. Any outputs emitted before its next cut therefore meet the original policy. Construction R removes exactly their keys and retains all other expected terms and deadlines. R3 maps the actual future state to the inherited interface without rejuvenating any birth; a replacement may alter future traces, but admission proves its own outputs against the same remaining policy. The strict equality of remaining-key maps prevents re-emission of removed keys or silent loss of required ones. Age invariance under rebasing maintains original rather than reset deadlines. This establishes the induction hypothesis for the new epoch. A finite number of edits has a last epoch, where E1 eventually fires all remaining output vertices. An infinite sequence, even of zero-time edits, need not have a last epoch and is deliberately excluded. QED.

The theorem is for the logical cut-and-install semantics. Correct ownership transfer of side-effectful actors, a physical network's late deliveries to an old deployment, persistent state migration, and linear resource use across two concurrently active runtimes require additional mechanisms and are not inferred from term equality or this admission theorem. A gate in a proposed graph is fully accounted for in its timing; its existence does not by itself establish a real protocol's correctness.

## 8. Certificate and implementation boundary

The mathematical certificate consists of a dependency order, each input zone's exact profile paths and feasible column potentials, the propagated rows, data-only lineages, constructor terms, and output obligations. Z2 proves exact initial cells; a union maximum proves the initial profile; each local max equation is checked over all declared dependencies. A topological order is checked rather than inferred by the replay kernel. E1 and F1 then justify its accepted output obligations. The actual Python replay kernel implements these checks but has not been verified in a proof assistant. Its finite mutation tests are evidence against specified implementation defects, not a general machine proof of the Python interpreter or program.

Let Z be the number of zones, V the number of their clock variables, E_c their constraint-edge count, E the continuation edge count, P the ports, S the origins, and T the total materialized constructor-term size. Floyd--Warshall closure takes O(Z V^3) arithmetic operations. The current simple tight-edge path extraction scans all constraint edges per visited clock and source, costing O(Z S V E_c), in addition to producing the paths. Certificate size is O(Z S(P V+V+P)+S(P+N)+T) integer/string items with explicit paths. Replay costs O(Z S E_c+Z S P V+S E+T), apart from ordinary bounded syntax/container operations. Prefix feasibility generation uses Bellman--Ford per conditioned zone, O(Z V E_c), while replay scans potentials or cycles. Affine substitution is linear in the listed constraints before duplicate-edge normalization. Exposing a cut can increase port and constraint counts; implementation caps reject oversized requests as resource failures, not stale-output witnesses.

For legal encoded inputs, integer operations use exact Python integers. Input constants have at most 128 magnitude bits. The certificate checker allows 256-bit derived values; finite path sums with at most 128 event vertices and bounded clock differences fit within that limit. Constructor strings are explicitly size/depth capped. There is no claim that expanded free terms are polynomial in graph size without accounting for T. Enumeration oracles are separately capped and raise errors rather than silently sampling a larger domain.

## 9. Counterexamples and retained non-claims

**Own-age scalars are insufficient.** At one cut let (b_a,b_b,r_p,r_q)=(-2,-2,0,0), and at another let it be (-2,0,0,2), with p carrying a and q carrying b. Both own ages are (2,2). A zero-delay copy of p gated by q has ages two and four respectively. The needed cross entry is r_q-b_a.

**Control lineage differs from control timing.** A data port born and ready at zero gated by a control port born at -100 but ready at zero produces an age-zero copy. Importing the gate's birth into the payload lineage would incorrectly report age 100. Ignoring the gate's readiness, conversely, is unsound in the preceding example.

**A new epoch is not a new generation.** A source born at -2 with an output at absolute time two has age four. After a cut at one its birth is -3 and the remaining output time is one, still age four. Leaving its birth at -2 underreports age as three; resetting it to zero underreports further.

**Strict residual lower bounds and distinct in-flight ports matter.** If a [0,1] message from time zero is not received by cut zero, its residual readiness is exactly one, not [0,1]. The latter adds an impossible immediate output while keeping the same worst age. Two independent [1,2] messages from a common sender yield four joint readiness pairs. Aliasing them to one boundary readiness retains only two pairs, again without changing the two marginal worst ages. These facts are recorded as complete small observation sets in the negative controls.

**Delay assumptions matter.** Two serial delays individually in [0,1] but constrained to have sum<=1 have maximum total one, not two. Rectangular interval analysis still gives a sound upper bound but not the exact all-upper witness. No such coupled-delay input is silently treated as satisfying the runtime residualization assumptions.

**Context restrictions matter.** With birth zero, readiness sets {0,2} and {1,2} have the same one-cell profile two. A forbidden timestamp-dependent context that waits five ticks exactly when readiness is zero yields worst ages five and two. C1 therefore does not extend to arbitrary clock-inspecting code.

**Unbounded waiting and shortest diagnostics are not covered.** One edge of unbounded delay defeats every finite freshness deadline for a fixed birth. The analyzer reports an attaining worst-age witness or a dependency cycle, not a globally shortest stale execution or shortest deadlock explanation. Neither finite case counts nor successful commands establish deployment performance or novelty. The precise scholarly comparison must be read separately from these mathematical arguments.
