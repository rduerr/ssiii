concentrationCodes = read.csv("concentrationCodes.csv",as.is=T)
plot(x=c(), xlim=c(0,1),ylim=c(0,20),xaxp=c(0,1,10),yaxt="n",
     xlab="Sea Ice Concentration", ylab="Probability for code")
for (i in rownames(concentrationCodes)) {
  lines(concentrationCodes[i,"Mean"]+xx,
        dnorm(xx,0,concentrationCodes[i,"StdDev"]),
        col=concentrationCodes[i,"Color"])
}
