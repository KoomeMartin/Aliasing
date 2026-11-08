I need you to help me build a program that will adapt to a tkinter UI in python. It needs to be able to do the following:

i)

- Capture an audio file of an arbitrary length from the PC 
- Ability to specifty the sampling rate of the audio signals atleast (8khz, 16 and 48 khz)
- for sample represenatation ensure that it supports atlest 16bits per sample and used a signed integer format 
- for 8 bits represenatation , you need to used and unsigned byte format 
- files should be saved in .wav format 
- we should the ability to playback a file thathas been captured ,

ii)

After the samples have been digitised, the system should be able to compute a spectograph an visualize it in graph, computer the power sprectrum on a block by block basis: the block size shaould be a variable 

For the graph visual:
-use deciBels on the y-axis relative to the highest power 

- fade from blue to red where blues is power relative to the max power and red as the max power (0dB).
- you need to have a noise floor and clip all the values below the noise floor. Suggested values -45bB: (Pure blue -45dB, pure red 0dB)
- Ensure to approapriately inlude both sine and cosine coeffeceints that are at the same frequemcy when computing the power 

iii)

- The user should be able to sub sample a selected file by simply taking every M'th sample. It should not filter before taking every M'th sample. 
- We then need to able write the sub-sampled audio to a .wav file, play it back and generate a spectograph 
- Once subsampled, I would like to upsample it by the same factor that it was downsampled with. Use the standard high quality multirate DSP filters and techniques for the upsampling.

iv)
 
- We need to keep note of the kth coefficent of 0,1,2,...,n/2 where N is the tranfrom size corresponding to frequency.
The plots should show the actual frequency based on the sapling rate 

v)

- Finally, we need to able to do a block by block filtering using the chosen block size. 
- User should be able to specify a desired lowpass cutoff frequency then forward tranform a block, throw away all the frequecies higher than that (set those tranforms coefficeints to 0)
- Make sure to reatain both the sine and cosine componets that are below the cutoff and reapeat this for eavery block 

