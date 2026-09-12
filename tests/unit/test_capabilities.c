#include "test.h"
#include "../../src/driver/features.h"
#include <string.h>

typedef struct {
    FeatureRegistry registry;
    Feature features[256]; FeatureTestGroup tests[256];
    FeatureExample examples[256]; OptimizationFamily families[256];
} RegistryFixture;
static void reset(RegistryFixture *f) {
    const FeatureRegistry *r=features_registry(); f->registry=*r;
    memcpy(f->features,r->features,r->feature_count*sizeof(Feature));
    memcpy(f->tests,r->tests,r->test_count*sizeof(FeatureTestGroup));
    memcpy(f->examples,r->examples,r->example_count*sizeof(FeatureExample));
    memcpy(f->families,r->families,r->family_count*sizeof(OptimizationFamily));
    f->registry.features=f->features; f->registry.tests=f->tests;
    f->registry.examples=f->examples; f->registry.families=f->families;
}
static void rejected(RegistryFixture *f,const char *kind) {
    FeatureIssue issue={0}; CHECK(!features_validate(&f->registry,&issue));
    CHECK_EQ_S(str_from(issue.kind ? issue.kind : ""),kind);
}
static Feature *mutable_feature(RegistryFixture *f,const char *id) {
    return (Feature *)features_find(&f->registry,id);
}
void run_capability_tests(void) {
    RegistryFixture f; Arena *a=arena_new(0); const FeatureRegistry *r=features_registry();
    CASE("capabilities: valid registry has separate status and evidence axes");
    FeatureIssue issue={0}; CHECK(features_validate(r,&issue)); CHECK(!issue.kind);
    const Feature *ir=features_find(r,"ir.codegen"); CHECK(ir); CHECK_EQ_I(ir?ir->state:-1,FEATURE_UNAVAILABLE);
    const Feature *owned=features_find(r,"native.owned_storage"); CHECK(owned); CHECK_EQ_I(owned?owned->state:-1,FEATURE_PARTIAL);
    CHECK_EQ_I(features_target("enfusion"),FEATURE_ENFUSION); CHECK_EQ_I(features_target("unknown"),0);
    Str all=features_catalog_json(a,NULL,FEATURE_ALL);
    CHECK_CONTAINS(all,"\"admission\":{\"status\":\"not_checked\"");
    CHECK_CONTAINS(all,"\"local_availability\":{\"status\":\"not_checked\"}");
    CHECK_CONTAINS(all,"\"applicable_evidence\":{\"status\":\"not_checked\",\"receipts\":[]");
    CHECK_CONTAINS(all,"\"released_plans\":[],\"measurements\":null");
    CHECK_MISSING(all,"\"execution\":\"success\"");

    CASE("capabilities: duplicate or malformed declarations fail closed");
    reset(&f); f.features[1].id=f.features[0].id; rejected(&f,"duplicate_feature");
    reset(&f); f.features[0].state=(FeatureState)55; rejected(&f,"invalid_feature");
    reset(&f); f.features[0].targets=64; rejected(&f,"invalid_feature");
    reset(&f); f.features[0].source="../outside.c"; rejected(&f,"invalid_feature");
    reset(&f); f.features[0].id="broken..id"; rejected(&f,"invalid_feature");

    CASE("capabilities: unknown, repeated and cyclic dependencies are rejected");
    reset(&f); f.features[0].dependencies[0]="unknown"; rejected(&f,"unknown_dependency");
    reset(&f); mutable_feature(&f,"language.modules")->dependencies[0]="language.plain_values"; rejected(&f,"dependency_cycle");
    reset(&f); mutable_feature(&f,"language.plain_values")->dependencies[1]="language.modules"; rejected(&f,"duplicate_link");
    reset(&f); for (size_t i=0;i<FEATURE_MAX_LINKS;i++) f.features[0].dependencies[i]=r->features[i].id;
    rejected(&f,"unterminated_links");

    CASE("capabilities: test obligations resolve to registered positive and negative groups");
    reset(&f); f.features[0].test_groups[0]="missing_group"; rejected(&f,"unknown_test_group");
    reset(&f); f.features[0].test_groups[0]=NULL; rejected(&f,"missing_test_group");
    reset(&f); f.tests[0].negative=""; rejected(&f,"invalid_test_group");
    reset(&f); f.tests[1].id=f.tests[0].id; rejected(&f,"duplicate_test_group");

    CASE("capabilities: examples cannot advertise unimplemented or uncovered targets");
    reset(&f); f.examples[0].features[0]="ir.codegen"; rejected(&f,"unavailable_example_feature");
    reset(&f); f.examples[0].targets=FEATURE_ENFUSION; rejected(&f,"uncovered_example_target");
    reset(&f); f.examples[0].sources[0]="C:/outside.be"; rejected(&f,"invalid_example_source");
    reset(&f); f.examples[1].id=f.examples[0].id; rejected(&f,"duplicate_example");
    Str engine=features_examples_json(a,NULL,FEATURE_ENFUSION);
    CHECK_CONTAINS(engine,"\"id\":\"pid.complete\""); CHECK_MISSING(engine,"arithmetic.native");
    CHECK_MISSING(engine,"records.native"); CHECK_CONTAINS(engine,"\"source_identity\":\"not_checked\"");

    CASE("capabilities: family inventory preserves the public optimization contract");
    CHECK(features_family_known("terrain-destination")); CHECK(!features_family_known("not-real"));
    Str family=features_families_json(a); CHECK_CONTAINS(family,"\"status\":\"proposed\",\"released\":false,\"eligible\":false");
    reset(&f); f.families[1].name=f.families[0].name; rejected(&f,"duplicate_family");
    reset(&f); f.families[1].hypothesis=f.families[0].hypothesis; rejected(&f,"duplicate_hypothesis");

    CASE("capabilities: stable fingerprint and filtering do not imply execution");
    Str one=features_fingerprint(a),two=features_fingerprint(a); CHECK_EQ_I(one.len,64); CHECK(str_eq(one,two));
    CHECK(!features_find(r,"unknown")); CHECK(!features_example_find(r,"unknown"));
    Str filtered=features_catalog_json(a,"ir.codegen",FEATURE_NATIVE);
    CHECK_CONTAINS(filtered,"\"id\":\"ir.codegen\""); CHECK_MISSING(filtered,"\"id\":\"native.ast\"");
    CHECK_CONTAINS(filtered,"\"implementation\":{\"status\":\"unavailable\"");
    arena_free(a);
}
