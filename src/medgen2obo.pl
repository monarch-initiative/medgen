#!/usr/bin/perl
use strict;

# Vars
my %th = ();
my %rh = ();
my %dh = ();
my %uh = ();
my %ssh = ();
my %styh = ();

our $PATH = "ftp.ncbi.nlm.nih.gov/pub/medgen";

# Execution
open(F,"gzip -dc $PATH/MGCONSO.RRF.gz|") || die;
while(<F>) {
    next if m@^#@;
    chomp;
    my ($CUI, $TS, $STT, $ISPREF, $AUI, $SAUI, $SCUI, $SDUI, $SAB, $TTY, $CODE, $STR, $SUPPRESS) = split(/\|/,$_);
    $STR =~ s/\{/\\\{/g;
    $STR =~ s/\}/\\\}/g;
    if (!$th{$CUI}->{name} || $TS eq 'P') {
        $th{$CUI}->{name} = $STR;
    }

    my $x = "$SAB:$CODE";
    if ($SAB eq 'HPO') {
        $x = $SDUI;
    }
    if ($SAB eq 'ORDO') {
        $x = $SDUI;
        $x =~ s/_/:/;
    }
    if ($x =~ /OMIM:MTHU/) {
        next;
    }
    push(@{$th{$CUI}->{synonyms}}, [$STR, $x]);
    $th{$CUI}->{xrefs}->{$x} = 1;
}
close(F);


open(F,"gzip -dc $PATH/MGREL.RRF.gz|") || die;
while(<F>) {
    next if m@^#@;
    chomp;
    my (
        $CUI1  , # first concept unique identifier
        $AUI1 , # first atom unique identifier, where an atom is one term from a source
        $STYPE1 , # the name of the column in MRCONSO.RRF that contains the first identifier to which the relationship is attached
        $REL , # relationship label
        $CUI2 , # second concept unique identifier
        $AUI2 , # second atom unique identifier, where an atom is one term from a source
        $RELA , # additional relationship label
        $RUI , # relationship unique identifier
        $SAB , # abbreviation for the source of the term (Defined here)
        $SL , # source of relationship label
        $SUPPRESS , # suppressed by UMLS curators
        ) = split(/\|/, $_);
    next if $REL eq 'SIB';
    next if $REL eq 'inverse_isa';
    my $rn = $RELA ? $RELA : $REL;
    $rh{$CUI2}->{$rn}->{$CUI1} = $SL;
}
close(F);



open(F,"gzip -dc $PATH/MGSTY.RRF.gz|") || die;
while(<F>) {
    next if m@^#@;
    chomp;
    my ($CUI, $TUI, $STN, $STY, $ATUI) = split(/\|/, $_);
    $ssh{$CUI}->{$STY} = 1;
    $styh{$STY}++;
}
close(F);


our $UID2CUI = "uid2cui.tsv";
open(F,$UID2CUI) || die("$UID2CUI not found");
while(<F>) {
    next if m@^#@;
    chomp;
    my ($u,$c) = split(/\t/,$_);
    $uh{$c} = $u;
    $th{$c}->{xrefs}->{"MEDGEN:$u"} = 1;
}
close(F);

#open(F,"gzip -dc $PATH/MGDEF.RRF.gz|") || die;
#while(<F>) {
#    chomp;
#    my ($CUI, $DEF, $SOURCE) = split(/\|/, $_);
#    $dh{$CUI}->{$SOURCE} = $DEF;
#}
#close(F);

print "ontology: medgen\n";
foreach (keys %styh) {
    my $ss = mk_subset($_);
    print "subsetdef: $ss \"$_\"\n";
}
print "\n";

sub add_triples {
    my ($prefix, $id) = @_;

    my $h = $th{$id};
    print "[Term]\n";
    print "id: $prefix:$id\n";
    print "name: $h->{name}\n";
    foreach my $x (keys %{$h->{xrefs}}) {
        $x =~ s@MSH:@MESH:@;
        $x =~ s@NCI:@NCIT:@;
        $x =~ s@SNOMEDCT_US:@SCTID:@;
        # TODO: change these to skos:exactMatch?
        print "xref: $x\n";
    }
    foreach (keys %{$ssh{$id} || {}}) {
        my $ss = mk_subset($_);
        print "subset: $ss\n";
    }
    foreach my $s (@{$h->{synonyms}}) {
        my ($str, $x)= @$s;
        $str = escq($str);
        print "synonym: \"$str\" RELATED [$x]\n";
    }
    my $trelh = $rh{$id};
    foreach my $rel (keys %{$trelh}) {
        my $vh = $trelh->{$rel};
        foreach my $v (keys %$vh) {
            unless ($v eq $id) {
                my $tag = "relationship: $rel";
                if ($rel eq 'isa') {
                    $tag = 'is_a:';
                }
                if ($rel eq 'mapped_to') {
                    # TODO: change these to skos:exactMatch?
                    $tag = 'equivalent_to:';  # This translates to owl:equivalentClass
                    # $tag = 'xref:';  # want to get this to translate to skos:exactMatch, but got oboInOwl:hasDbXref instead
                }
                # Namespaces: Different ones based on if is a UMLS CUI (C#), a MEDGEN CUI Novel (CN#), or a MedGEn UID (#).
                if ($v =~ /^CN\d+/) {
                    print "$tag MEDGENCUI:$v {source=\"$vh->{$v}\"} ! $th{$v}->{name}\n";
                # If a CUI (starts with 'C'), will be created twice: one for MEDGENCUI, one for UMLS
                } elsif ($v =~ /^C\d+/) {
                    print "$tag UMLS:$v {source=\"$vh->{$v}\"} ! $th{$v}->{name}\n";
                    print "$tag MEDGENCUI:$v {source=\"$vh->{$v}\"} ! $th{$v}->{name}\n";
                # UID
                } else {
                    print "$tag MEDGEN:$v {source=\"$vh->{$v}\"} ! $th{$v}->{name}\n";
                }
            }
        }
    }
    print "\n";
}
my @ids = keys %th;
@ids = sort @ids;
foreach my $id (@ids) {
    # Namespaces: Different ones based on if is a UMLS CUI (C#), a MedGen CUI Novel (CN#), or a MedGEn UID (#).
    if ($id =~ /^CN\d+/) {
        add_triples('MEDGENCUI', $id);
    # If a CUI (starts with 'C'), will be created twice: one for MEDGENCUI, one for UMLS
    } elsif ($id =~ /^C\d+/) {
        add_triples('UMLS', $id);
        add_triples('MEDGENCUI', $id);
    # UID
    } else {
        add_triples('MEDGEN', $id);
    }
}

exit 0;

sub mk_subset {
    my $sty = shift;
    $sty =~ s/\s+/-/g;
    return $sty;
}

sub escq {
    my $s = shift;
    $s =~ s/\"/\'/g;
    $s =~ s/\r/ /g;
    $s =~ s/\n/ /g;
    return $s;
}
