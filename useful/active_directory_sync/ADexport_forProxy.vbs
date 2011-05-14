'==========================================================================
'
' VBScript Source File -- Created with SAPIEN Technologies PrimalScript 4.0
'
' NAME: ADexport_forProxy.vbs
'
' AUTHOR: VIERRI (Robert Riegler)
' DATE  : 24.03.2009
' VERSION: 1.01
'
' COMMENT: 
' Retrieve only all "enabled" AD User Objects which are members of one of following groups: (for both domains MMG und MMK) 
'	- cn=MM-Internet,ou=!Ress,dc=mmk,dc=mmdom,dc=net"
'	- cn=MMG-Internet,ou=!Ress,dc=mmg,dc=mmdom,dc=net"
'	- cn=MMDOM-Internet,ou=!Ress,dc=mmdom,dc=net"
'
' v1.00 / VIERRI / Initial Script
' v1.01 / VIERRI / Don´t output Header line 
'==========================================================================

Const ForReading = 1
Const ForWriting = 2
Const ForAppending = 8
Const MaxDisplayLen = 24

Dim arrProperties
Dim arrProp()
Dim strCanonicalName,strSamAccountName,strdisplayName,strProxyAddresses,strDistinguishedName
Dim strProxyAddress, strOU
Dim strGroupDN, strUserDN, strMemberFilterGlobal, objGroup, objGroupList
Dim objRootDSE, adoCommand, adoConnection
Dim strBase, strLDAPBase, strAttributes
Dim bDebug
Dim bInGroup
Dim strCsvFilename
Dim anzLdapSearch, anzLdapSearchFound

strProperties = "canonicalName,sAMAccountName,distinguishedName,displayName,proxyAddresses"
strGroupDN_MMK = "cn=MM-Internet,ou=!Ress,dc=mmk,dc=mmdom,dc=net"
strDomain_MMK = "MMK"
strGroupDN_MMG = "cn=MMG-Internet,ou=!Ress,dc=mmg,dc=mmdom,dc=net"
strDomain_MMG = "MMG"
strGroupDN_MMDOM = "cn=MMDOM-Internet,ou=!Ress,dc=mmdom,dc=net"
strDomain_MMDOM = "MMDOM"
strGroupDN = strGroupDN_MMK

'strTestUser = "LDAP://dc-vie-50.mmk.mmdom.net/CN=Riegler Robert,OU=WKS-User,OU=User,OU=IT,OU=VIE,DC=mmk,DC=mmdom,DC=net"
strLdapServer = "srv-vie-03"

strFilename = "C:\Tools\Proxy\User"
strDim = ";"
bDebug = false
scriptVersion = "1.01"


strFilter = ""
strFilter0 = "(&(&(objectCategory=person)(objectClass=user))(!(extensionAttribute6=1)))"
strFilter1 = "(&(&(objectCategory=person)(objectClass=user))(extensionAttribute6=1))"
strFilter2 = "(&(objectCategory=person)(objectClass=user))"
strFilterEnabled = "(!(userAccountControl:1.2.840.113556.1.4.803:=2))"
strFilterDisabled = "(userAccountControl:1.2.840.113556.1.4.803:=2)"


Set objFSO = CreateObject("Scripting.FileSystemObject")
Set objArgs = WScript.Arguments

If objArgs.Count <> 0 Then
	If objArgs(0) = "/?" Then
		WScript.Echo "SYNTAX:"
	    WScript.Echo "	ADexport_forProxy.vbs <LDAP-Server> <LOC> <System-Filter1> <System-Filter2>"
	    WScript.Echo "		<LDAP-Server> ... DC used for query against"
    	WScript.Echo "		<LOC> ... Location shortname in AD (first OU layer)"
    	WScript.Echo "		    ALL .. complete AD for Domain specified by <LDAP-Server>"
    	WScript.Echo "		<System-Filter1> ... 0|1|2 --> must not be specified"
    	WScript.Echo "			0 ... gets only REAL Users, No SystemUsers (DEFAULT)"
    	WScript.Echo "			1 ... gets only SYSTEM Users"
    	WScript.Echo "			2 ... gets ALL Users"
    	WScript.Echo "		<System-Filter2> ... 0|1|2 --> must not be specified"
    	WScript.Echo "			0 ... gets only ENABLED Users (DEFAULT)"
    	WScript.Echo "			1 ... gets only DISABLED Users"
    	WScript.Echo "			2 ... gets ALL Users (ENABLED / DISABLED)"
    	WScript.Echo
    	WScript.Echo "	All Data comes out of AD (User-Objects), which can be filtered down"
    	WScript.Echo "	The output are 2 different Files; one for internal Users (Siemens HIPATH); one for external Users"
    	WScript.Echo "	There is a Config-File: SiemensTel_Kopfnummern.ini which is used to deside where to write the data"
    	WScript.Echo "		* If the Kopfnummer is in the File --> the data gets written into the INTERNAL File"
    	WScript.Echo
	    WScript.Echo "	zB.: MMK --> cscript ADexport_forProxy.vbs dc-vie-50 ALL (gets all MMK enabled REAL Users, No SystemUsers)"
	    WScript.Echo "	zB.: MMK --> cscript ADexport_forProxy.vbs dc-vie-50 SLG 0 (gets only REAL Users, No SystemUsers)"
    	WScript.Echo "	zB.: MMK --> cscript ADexport_forProxy.vbs dc-vie-50 SLG 1 (gets only SYSTEM Users)"
	    WScript.Echo "	zB.: MMK --> cscript ADexport_forProxy.vbs dc-vie-50 SLG 2 (gets ALL Users)"
   	    WScript.Echo "	zB.: MMK --> cscript ADexport_forProxy.vbs dc-vie-50 ALL (gets all MMK enabled REAL Users, No SystemUsers)"
    	WScript.Echo "	zB.: MMG --> cscript ADexport_forProxy.vbs dc-gvie-50 GIN 1"
    	WScript.Echo "	zB.: MMG --> cscript ADexport_forProxy.vbs dc-gvie-50 GIN (gets only REAL ENABLED Users, No SystemUsers)"

	    WScript.Quit
    Else
	   	strLdapServer = objArgs(0)
		If objArgs.Count > 1 Then
			strArg = objArgs(1)
			If objArgs.Count > 2 Then
				strF = objArgs(2)
				Select Case strF
					Case "0"
						If objArgs.Count > 3 Then
							strF1 = objArgs(3)
							Select Case strF1
								Case "0"
									strFilter = "(&" & strFilter0 & strFilterEnabled & ")"
								Case "1"
									strFilter = "(&" & strFilter0 & strFilterDisabled & ")"
								Case "2"
									strFilter = strFilter0
								Case Else
									WScript.Echo "Only 0/1/2 are allowed as 4th Parameter"
									WScript.Quit
							End Select
						Else
							strFilter = "(&" & strFilter0 & strFilterEnabled & ")"
						End If
					Case "1"
						If objArgs.Count > 3 Then
							strF1 = objArgs(3)
							Select Case strF1
								Case "0"
									strFilter = "(&" & strFilter1 & strFilterEnabled & ")"
								Case "1"
									strFilter = "(&" & strFilter1 & strFilterDisabled & ")"
								Case "2"
									strFilter = strFilter1
								Case Else
									WScript.Echo "Only 0/1/2 are allowed as 4th Parameter"
									WScript.Quit
							End Select
						Else
							strFilter = "(&" & strFilter1 & strFilterEnabled & ")"
						End If
					Case "2"
						If objArgs.Count > 3 Then
							strF1 = objArgs(3)
							Select Case strF1
								Case "0"
									strFilter = "(&" & strFilter2 & strFilterEnabled & ")"
								Case "1"
									strFilter = "(&" & strFilter2 & strFilterDisabled & ")"
								Case "2"
									strFilter = strFilter2
								Case Else
									WScript.Echo "Only 0/1/2 are allowed as 4th Parameter"
									WScript.Quit
							End Select
						Else
							strFilter = "(&" & strFilter2 & strFilterEnabled & ")"
						End If
					Case Else
						WScript.Echo "Only 0/1/2 are allowed as 3rd Parameter"
						WScript.Quit
				End Select
			Else
				strFilter = "(&" & strFilter0 & strFilterEnabled & ")"
			End If
		End If
	End If
End If


strLdapRootDSE = "LDAP://" & strLdapServer  & "/RootDSE"
Set rootDSE = GetObject(strLdapRootDSE)
domainContainer =  rootDSE.Get("defaultNamingContext")
WScript.Echo "Server: " & strLdapServer & " / Domain:" & domainContainer

Set objConnection = CreateObject("ADODB.Connection")
Set objCommand =   CreateObject("ADODB.Command")
objConnection.Provider = "ADsDSOObject"
objConnection.Open "Active Directory Provider"
Set objCommand.ActiveConnection = objConnection
objCommand.Properties("Page Size") = 1000

If UCase(domainContainer) = "DC=MMK,DC=MMDOM,DC=NET" then
	strGroupDN = strGroupDN_MMK
	strDomain = strDomain_MMK
End If
If UCase(domainContainer) = "DC=MMG,DC=MMDOM,DC=NET" then
	strGroupDN = strGroupDN_MMG
	strDomain = strDomain_MMG
End If
If UCase(domainContainer) = "DC=MMDOM,DC=NET" then
	strGroupDN = strGroupDN_MMDOM
	strDomain = strDomain_MMDOM
End If


'Get Date and Time
start_date = Date
start_time = Time
If len(DatePart("m",start_date)) = 1 Then
	strMonth = "0" & DatePart("m",start_date)
Else
	strMonth = DatePart("m",start_date)
End If
If len(DatePart("d",start_date)) = 1 Then
	strDay = "0" & DatePart("d",start_date)
Else
	strDay = DatePart("d",start_date)
End If
If len(DatePart("h",start_time)) = 1 Then
	strHour = "0" & DatePart("h",start_time)
Else
	strHour = DatePart("h",start_time)
End If
If len(DatePart("n",start_time)) = 1 Then
	strMinute = "0" & DatePart("n",start_time)
Else
	strMinute = DatePart("n",start_time)
End If
If len(DatePart("s",start_time)) = 1 Then
	strSecond = "0" & DatePart("s",start_time)
Else
	strSecond = DatePart("s",start_time)
End If
strStartDate = DatePart("yyyy",start_date) & strMonth & strDay & "_" & strHour & strMinute & strSecond

strLogFilename = strFilename & ".log"
Set objLogFile = objFSO.OpenTextFile(strLogFilename,8,TRUE,0)


strLDAPBase = "<LDAP://" & strLdapServer & "/"
'Define Filenames and generate Query
If objArgs.Count > 1 Then
	If UCase(strArg) = "ALL" Then
		strLdap = strLDAPBase & domainContainer & ">;" & strFilter & ";adspath;subtree"
		arrTemp = Split(domainContainer,",")
		strTemp = Right(arrTemp(0),Len(arrTemp(0))-3)
		strCsvFilename = strFilename & "_" & strTemp & ".csv"
	Else
		strLdap = strLDAPBase & "OU=" & strArg & "," & domainContainer & ">;" & strFilter & ";adspath;subtree"
		strCsvFilename = strFilename & ".csv"
	End If
Else
	strLdap = strLDAPBase & domainContainer & ">;" & strFilter & ";adspath;subtree"
	strCsvFilename = strFilename & ".csv"
End If

If bDebug Then
	Wscript.Echo "strLDAP: " & strLdap
End If

objCommand.CommandText = strLdap

WScript.Echo "processing AD..."
wscript.Echo strCsvFilename
Set objCsvFile = objFSO.CreateTextFile(strCsvFilename)

anzLdapSearch = 0
anzLdapSearchFound = 0

arrProperties = Split(strProperties,",")
ReDim arrProp(UBound(arrProperties),1)
For i = 0 To UBound(arrProperties)
	arrProp(i,0) = arrProperties(i)
Next

'objCsvFile.WriteLine "distinguishedName" & strDim & "OU" & strDim & "sAMAccountName" & strDim & "displayName" & strDim & "proxyAddress"
' v1.01 / VIERRI / Don´t output Header line
'objCsvFile.WriteLine "OU" & strDim & "sAMAccountName" & strDim & "displayName" & strDim & "proxyAddress"

On Error Resume Next
Set rsLdapSearch = objCommand.Execute

If Not isNull(rsLdapSearch) Then
	While Not rsLdapSearch.EOF
		bInGroup = False
		objGroupList = empty
		strLdapPath = rsLdapSearch.Fields("adspath").Value
		'strLdapPath = strTestUser
		strTemp1 = SPLIT(strLdapPath,"//")
		strTemp2 = SPLIT(strTemp1(1),"/")
		strUserDN = strTemp2(1)
		strMemberFilterGlobal = "(member=" & strUserDN & ")"
		anzLdapSearch = anzLdapSearch + 1		
		
		Set FoundObj = GetObject (strLdapPath)
		If bDebug Then
			Wscript.Echo "strLdapPath: " & strLdapPath
			Wscript.Echo "strMemberFilterGlobal: " &  strMemberFilterGlobal
		End If
		bInGroup = IsMember(UCase(strGroupDN))
		If bDebug Then
			Wscript.Echo "bInGroup: " & bInGroup
		End If

		If (bInGroup = True) Then
			anzLdapSearchFound = anzLdapSearchFound + 1
   			If bDebug Then
   				WScript.Echo anzLdapSearchFound & ".) " & strLdapPath
			End If
   			If anzLdapSearchFound Mod 50 = 0 Then
   				WScript.Echo "processing AD element (" & anzLdapSearchFound & ")"
				'Wscript.QUIT
			End If
   			
	   		FoundObj.GetInfo
			strOU = ""
			strCanonicalName = ""
			strSamAccountName = ""
			strDisplayName = ""
			strProxyAddresses = ""
			strProxyAddress = ""
			strOutput = ""
   				
	   		For j = 0 To UBound(arrProp,1)
   				valueProperty = ""
					
   				FoundObj.GetInfoEx Array(arrProp(j,0)), 0
	   			On Error Resume Next
				valueProperty = FoundObj.Get(arrProp(j,0))
   				arrProp(j,1) = valueProperty

	   			select Case UCase(arrProp(j,0))
   					Case UCase("canonicalName")
   						strCanonicalName = valueProperty
						strTemp1 = SPLIT(strCanonicalName,"/")
						
						If UCase(strTemp1(1)) = "SO" then
							'Wscript.echo "Canonical Name(SO): " & strCanonicalName
							strOU = strTemp1(2)
						Else
							strOU = strTemp1(1)
						End If
					
   					Case UCase("sAMAccountName")
	   					strSamAccountName = LCase(valueProperty)
					Case UCase("distinguishedName")
	   					strDistinguishedName = valueProperty
   					Case UCase("displayName")
   						strDisplayName = valueProperty
   						strDisplayName = Trim(strDisplayName)
   					Case UCase("proxyAddresses")
	   					strProxyAddresses = valueProperty
						for k= 0 to UBound(strProxyAddresses)
							strTemp1 = strProxyAddresses(k)
							strTemp1 = SPLIT(strTemp1,":")
							if strTemp1(0) = "SMTP" then
								strProxyAddress = strTemp1(1)
							end If
						next
   		   			End Select
   			Next
   		
	   		If bDebug Then
   				WScript.Echo strCanonicalName
   			End If
   		
			'strOutput = strDistinguishedName & strDim & strOU & strDim & strSamAccountName & strDim & strDisplayName & strDim & strProxyAddress
			strOutput = strOU & strDim & strSamAccountName & strDim & strDisplayName & strDim & strProxyAddress
			'if strOutput = "" then
			'	Wscript.echo "LEER"
			'Else
			'	Wscript.echo "stroutput: " & strOutput
			'End if
   			objCsvFile.WriteLine strOutput
			    		
		End If

		'If bDebug Then
		'	If anzLdapSearch Mod 16 = 0 Then
		'		WScript.Echo "processing AD element (" & anzLdapSearch & ")"
		'		Wscript.QUIT
		'	End If
		'End If

		rsLdapSearch.MoveNext
	Wend
End If

strOutput = anzLdapSearch & " USER-Objects processed; " & anzLdapSearchFound & " USER-Objects found!"
WScript.Echo strOutput
objLogFile.WriteLine strStartDate & ";" & strDomain & ";" & anzLdapSearchFound & " USER-Objects found in Internet enabled groups found."

objCsvFile.Close
objLogFile.Close



Function IsMember(ByVal strGroup)
    ' Function to test group membership.
    ' strGroup is the Distinguished Name of the group.
    ' objGroupList is a dictionary object with global scope.
    ' strUserDN is the Distinguished Name of the user, with
    ' global scope. ADO is used to search for all groups that
    ' have the user as a member.

    If (IsEmpty(objGroupList) = True) Then
        Set objGroupList = CreateObject("Scripting.Dictionary")
        objGroupList.CompareMode = vbTextCompare

        ' Determine DNS domain name.
        'Set objRootDSE = GetObject("LDAP://RootDSE")
        'strDNSDomain = objRootDSE.Get("DefaultNamingContext")

        ' Use ADO to search Active Directory.
        Set adoCommand = CreateObject("ADODB.Command")
        Set adoConnection = CreateObject("ADODB.Connection")
        adoConnection.Provider = "ADsDSOObject"
        adoConnection.Open "Active Directory Provider"
        adoCommand.ActiveConnection = adoConnection
        strBase = strLDAPBase & domainContainer & ">"
        strAttributes = "distinguishedName"
        adoCommand.Properties("Page Size") = 100
        adoCommand.Properties("Timeout") = 30
        adoCommand.Properties("Cache Results") = False

	Call LoadGroups(strMemberFilterGlobal)
        adoConnection.Close
    End If
  
    If bDebug Then  
	    Wscript.Echo "strGroup: " & strGroup
  
	    for each objGroup in objGroupList	
		Wscript.echo "Group-Dict: " & objGroup
	    next 	
    End If
    IsMember = objGroupList.Exists(strGroup)
    'Wscript.Echo "IsMember: " & IsMember
End Function

Sub LoadGroups(ByVal strMemberFilter)
    ' Recursive subroutine to populate a dictionary object with group
    ' memberships. strMemberFilter is the filter used by ADO to find
    ' groups having the members specified. When this subroutine is first
    ' called by Function IsMember, strMemberFilter specifies the user.
    ' On recursive calls, strMemberFilter specifies all groups returned
    ' by the previous call of the subroutine. The subroutine is called
    ' once for each level of group nesting.

    Dim strFilter, strQuery, strDN, adoRecordset
    Dim strNextFilter, blnRecurse

'On Error Goto 0
    
    strFilter = "(&(objectCategory=Group)" & strMemberFilter & ")"
    strQuery = strBase & ";" & strFilter & ";" & strAttributes & ";subtree"
    If bDebug Then
	    Wscript.Echo "strQuery: " & strQuery
    End If
    adoCommand.CommandText = strQuery

    Set adoRecordset = adoCommand.Execute
    strNextFilter = "(|"
    blnRecurse = False
    
    anz = 0
    Do Until adoRecordset.EOF
        strDN = UCase(adoRecordset.Fields("DistinguishedName").Value)
	anz = anz +1
	
        If (objGroupList.Exists(strDN) = False) Then
	    If bDebug Then
		Wscript.Echo "strDN: " & strDN
	    End If
	    
	    objGroupList.Add strDN, True
            strNextFilter = strNextFilter & "(member=" & strDN & ")"
            blnRecurse = True
        End If
        adoRecordset.MoveNext
    Loop
    'Wscript.Echo "#: " & anz
    adoRecordset.Close

    If bDebug Then
	    for each objGroup in objGroupList	
		Wscript.echo "Group-Dict: " & objGroup
	    next
	    Wscript.Echo "#: " & objGroupList.Count
	    Wscript.Echo "blnRecurse: " & blnRecurse 
    End If

    If (blnRecurse = True) Then
        strNextFilter = strNextFilter & ")"
        Call LoadGroups(strNextFilter)
    End If
End Sub