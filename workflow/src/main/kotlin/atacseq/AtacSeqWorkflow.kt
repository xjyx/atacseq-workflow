package atacseq

import atacseq.model.FastqSamples
import atacseq.task.*
import krews.core.workflow
import krews.run
import reactor.core.publisher.toFlux

fun main(args: Array<String>) = run(atacSeqWorkflow, args)

data class AtacSeqParams(
        val samples: FastqSamples,
        val trimAdaptor: TrimAdapterParams,
        val bowtie2: Bowtie2Params,
        val filter: FilterParams,
        val bam2ta: Bam2taParams,
        val macs2: Macs2Params
)

val atacSeqWorkflow = workflow("atac-seq-workflow") {
    val params = params<AtacSeqParams>()

    val trimAdaptorInputs = params.samples.replicates
            .map { TrimAdapterInput(it, params.trimAdaptor) }
            .toFlux()
    val trimAdaptorTask = trimAdaptorTask(trimAdaptorInputs)

    val bowtie2Input = trimAdaptorTask.output
            .map { Bowtie2Input(it.mergedReplicate, params.bowtie2) }
    val bowtie2Task = bowtie2Task(bowtie2Input)

    val filterInput = bowtie2Task.output
            .map { FilterInput(it.bam, it.repName, it.pairedEnd, params.filter) }
    val filterTask = filterTask(filterInput)

    val bam2taInput = filterTask.output
            .map { Bam2taInput(it.noDupBam, it.repName, it.pairedEnd, params.bam2ta) }
    val bam2taTask = bam2taTask(bam2taInput)

    val macs2Input = bam2taTask.output
            .map { Macs2Input(it.ta, it.repName, it.pairedEnd, params.macs2) }
    macs2Task(macs2Input)
}