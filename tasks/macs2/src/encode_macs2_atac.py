#!/usr/bin/env python

# ENCODE DCC MACS2 call peak wrapper
# Author: Jin Lee (leepc12@gmail.com)

import sys
import os
import argparse
from common.encode_common import *
from common.encode_common_genomic import peak_to_bigbed
from common.encode_blacklist_filter import blacklist_filter
from common.encode_frip import frip

def parse_arguments():
    parser = argparse.ArgumentParser(prog='ENCODE DCC MACS2 callpeak',
                                        description='')
    parser.add_argument('ta', type=str,
                        help='Path for TAGALIGN file.')
    parser.add_argument("--output-prefix", type = str, default = 'output',
                        help = "output file name prefix; defaults to 'output'")
    parser.add_argument('--chrsz', type=str,
                        help='2-col chromosome sizes file.')
    parser.add_argument('--gensz', type=str, default = '',
                        help='Genome size (sum of entries in 2nd column of \
                            chr. sizes file, or hs for human, ms for mouse).')
    parser.add_argument('--pval-thresh', default=0.01, type=float,
                        help='P-Value threshold.')
    parser.add_argument('--smooth-win', default=150, type=int,
                        help='Smoothing window size.')
    parser.add_argument('--cap-num-peak', default=300000, type=int,
                        help='Capping number of peaks by taking top N peaks.')
    parser.add_argument('--make-signal', action="store_true",
                        help='Generate signal tracks for P-Value and fold enrichment.')
    parser.add_argument('--blacklist', type=str, 
                        help='Blacklist BED file.')
    parser.add_argument('--out-dir', default='', type=str,
                        help='Output directory.')
    parser.add_argument('--paired-end', action="store_true", default=False)
    parser.add_argument('--log-level', default='INFO', 
                        choices=['NOTSET','DEBUG','INFO',
                            'WARNING','CRITICAL','ERROR','CRITICAL'],
                        help='Log level')
                        
    args = parser.parse_args()
    log.info(args.blacklist)    
    if args.blacklist.endswith('/dev/null'):
        args.blacklist = ''

    if args.gensz == '':
        with open(args.chrsz, 'r') as f:
            args.gensz = sum([ int(x.strip().split('\t')[-1]) for x in f ])

    log.setLevel(args.log_level)
    log.info(sys.argv)
    return args

def macs2(ta, chrsz, gensz, pval_thresh, smooth_win, cap_num_peak, 
          make_signal, out_dir, paired_end = False, prefix = "output"):
    prefix = os.path.join(out_dir, prefix)
    npeak = '{}.{}.{}.narrowPeak.gz'.format(
        prefix,
        'pval{}'.format(pval_thresh),
        human_readable_number(cap_num_peak))
    pileup_bigwig = '{}.pileup.bigwig'.format(prefix)
    fc_bigwig = '{}.fc.signal.bigwig'.format(prefix)
    pval_bigwig = '{}.pval.signal.bigwig'.format(prefix)
    # temporary files
    npeak_tmp = '{}.tmp'.format(npeak)
    fc_bedgraph = '{}.fc.signal.bedgraph'.format(prefix)
    fc_bedgraph_srt = '{}.fc.signal.srt.bedgraph'.format(prefix)
    pval_bedgraph = '{}.pval.signal.bedgraph'.format(prefix)
    pval_bedgraph_srt = '{}.pval.signal.srt.bedgraph'.format(prefix)

    shiftsize = -int(round(float(smooth_win)/2.0))
    temp_files = []

    cmd0 = 'macs2 callpeak '
    cmd0 += '-t {} -f BED{} -n {} -g {} -p {} '
    cmd0 += '--shift {} --extsize {} --tempdir {} '
    cmd0 += '--nomodel -B --SPMR '
    cmd0 += '--keep-dup all --call-summits '
    cmd0 = cmd0.format(
        ta,
        "PE" if paired_end else "",
        prefix,
        gensz,
        pval_thresh,
        shiftsize,
        smooth_win,
        out_dir)
    run_shell_cmd(cmd0)

    cmd1 = 'LC_COLLATE=C sort -k 8gr,8gr "{}_peaks.narrowPeak" | '
    cmd1 += 'awk \'BEGIN{{OFS="\\t"}}{{$4="Peak_"NR; if ($2<0) $2=0; if ($3<0) $3=0; print $0}}\' > {}'
    cmd1 = cmd1.format(
        prefix,
        npeak_tmp)
    run_shell_cmd(cmd1)

    cmd2 = 'head -n {} {} | gzip -nc > {}'.format(
        cap_num_peak,
        npeak_tmp,
        npeak)
    run_shell_cmd(cmd2)
    rm_f(npeak_tmp)

    if make_signal:
        cmd4 = 'bedtools slop -i "{}_treat_pileup.bdg" -g {} -b 0 | '
        cmd4 += 'bedClip stdin {} {}_treat_pileup.clipped.bdg'
        cmd4 = cmd4.format(
            prefix,
            chrsz, 
            chrsz, 
            prefix)
        run_shell_cmd(cmd4)
      
        cmd5 = 'LC_COLLATE=C sort -k1,1 -k2,2n {}_treat_pileup.clipped.bdg > {}_treat_pileup.sorted.bdg'
        cmd5 = cmd5.format(
            prefix,
            prefix)
        run_shell_cmd(cmd5)

        cmd5_1 = 'bedtools merge -i {}_treat_pileup.sorted.bdg -c 4 -o mean -d -1 > {}_treat_pileup.sorted.merged.bdg'
        cmd5_1 = cmd5_1.format(
            prefix,
            prefix)
        run_shell_cmd(cmd5_1)

        cmd6 = 'bedGraphToBigWig {}_treat_pileup.sorted.merged.bdg {} {}'
        cmd6 = cmd6.format(
            prefix,
            chrsz,
            pileup_bigwig)
        run_shell_cmd(cmd6)
        
        cmd3 = 'macs2 bdgcmp -t "{}_treat_pileup.bdg" '
        cmd3 += '-c "{}_control_lambda.bdg" '
        cmd3 += '--o-prefix "{}" -m FE '
        cmd3 = cmd3.format(
            prefix, 
            prefix, 
            prefix)
        run_shell_cmd(cmd3)

        cmd4 = 'bedtools slop -i "{}_FE.bdg" -g {} -b 0 | '
        cmd4 += 'bedClip stdin {} {}'
        cmd4 = cmd4.format(
            prefix, 
            chrsz, 
            chrsz, 
            fc_bedgraph)
        run_shell_cmd(cmd4)
      
        cmd5 = 'LC_COLLATE=C sort -k1,1 -k2,2n {} > {}_FC_SIGNAL_TO_MERGE.bdg'
        cmd5 = cmd5.format(
            fc_bedgraph,
            prefix)
        run_shell_cmd(cmd5)

        cmd5_1 = 'bedtools merge -i {}_FC_SIGNAL_TO_MERGE.bdg -c 4 -o mean -d -1 > {}'
        cmd5_1 = cmd5_1.format(
            prefix,
            fc_bedgraph_srt)
        run_shell_cmd(cmd5_1)

        cmd6 = 'bedGraphToBigWig {} {} {}'
        cmd6 = cmd6.format(
            fc_bedgraph_srt,
            chrsz,
            fc_bigwig)
        run_shell_cmd(cmd6)

        # sval counts the number of tags per million in the (compressed) BED file
        sval = float(get_num_lines(ta))/1000000.0
        
        cmd7 = 'macs2 bdgcmp -t "{}_treat_pileup.bdg" '
        cmd7 += '-c "{}_control_lambda.bdg" '
        cmd7 += '--o-prefix {} -m ppois -S {}'
        cmd7 = cmd7.format(
            prefix,
            prefix,
            prefix,
            sval)
        run_shell_cmd(cmd7)

        cmd8 = 'bedtools slop -i "{}_ppois.bdg" -g {} -b 0 | '
        cmd8 += 'bedClip stdin {} {}'

        cmd8 = cmd8.format(
            prefix,
            chrsz,
            chrsz,
            pval_bedgraph)
        run_shell_cmd(cmd8)

        cmd9 = 'LC_COLLATE=C sort -k1,1 -k2,2n {} > {}_PVAL_SIGNAL_TO_MERGE.bdg'
        cmd9 = cmd9.format(
            pval_bedgraph,
            prefix)
        run_shell_cmd(cmd9)

        cmd9_1 = 'bedtools merge -i {}_PVAL_SIGNAL_TO_MERGE.bdg -c 4 -o mean -d -1 > {}'
        cmd9_1 = cmd9_1.format(
            prefix,
            pval_bedgraph_srt)
        run_shell_cmd(cmd9_1)

        cmd10 = 'bedGraphToBigWig {} {} {}'
        cmd10 = cmd10.format(
            pval_bedgraph_srt,
            chrsz,
            pval_bigwig)
        run_shell_cmd(cmd10)
    else:
        # make empty signal bigwigs (WDL wants it in output{})
        fc_bigwig = '/dev/null'
        pval_bigwig = '/dev/null'

    # remove temporary files
    temp_files.extend([ fc_bedgraph, fc_bedgraph_srt,
                        pval_bedgraph, pval_bedgraph_srt ])
    temp_files.append("{}_*".format(prefix))
    rm_f(temp_files)

    return npeak, fc_bigwig, pval_bigwig

def main():
    # read params
    args = parse_arguments()

    log.info('Initializing and making output directory...')
    mkdir_p(args.out_dir)

    log.info('Calling peaks and generating signal tracks with MACS2...')
    npeak, fc_bigwig, pval_bigwig = macs2(
        args.ta, args.chrsz, args.gensz, args.pval_thresh,
        args.smooth_win, args.cap_num_peak, args.make_signal, 
        args.out_dir, args.paired_end, args.output_prefix)

    log.info('Checking if output is empty...')
    assert_file_not_empty(npeak)

    log.info('Blacklist-filtering peaks...')
    bfilt_npeak = blacklist_filter(
            npeak, args.blacklist, False, args.out_dir)

    log.info('Converting peak to bigbed...')
    peak_to_bigbed(bfilt_npeak, 'narrowPeak', args.chrsz, args.out_dir)

    if args.ta: # if TAG-ALIGN is given
        log.info('FRiP without fragment length...')
        frip_qc = frip( args.ta, bfilt_npeak, args.out_dir)
    else:
        frip_qc = '/dev/null'

    log.info('List all files in output directory...')
    ls_l(args.out_dir)

    log.info('All done.')

if __name__=='__main__':
    main()
